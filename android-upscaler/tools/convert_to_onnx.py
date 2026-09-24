import zipfile, pickle, sys, numpy as np, onnx
from onnx import helper, TensorProto, numpy_helper

def load_pth(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    root = names[0].split('/')[0]
    class Storage:  # placeholder for storage type
        def __init__(s, name): s.name = name
    dtypes = {'FloatStorage': np.float32, 'HalfStorage': np.float16, 'DoubleStorage': np.float64, 'LongStorage': np.int64}
    def rebuild(storage, offset, size, stride, *a):
        dt, key = storage
        buf = np.frombuffer(z.read(f'{root}/data/{key}'), dtype=dt)
        if len(size) == 0: return buf[offset].copy()
        itemsize = buf.itemsize
        return np.lib.stride_tricks.as_strided(buf[offset:], shape=size, strides=[s*itemsize for s in stride]).copy()
    class U(pickle.Unpickler):
        def find_class(self, mod, name):
            if name == '_rebuild_tensor_v2': return rebuild
            if name in dtypes: return dtypes[name]
            if mod == 'collections' and name == 'OrderedDict':
                import collections; return collections.OrderedDict
            return super().find_class(mod, name)
        def persistent_load(self, pid):
            _, stype, key, loc, n = pid
            return (stype, key)
    return U(z.open(f'{root}/data.pkl')).load()

def build(pth, out, num_conv):
    sd = load_pth(pth)
    sd = sd.get('params_ema', sd.get('params', sd))
    inits, nodes = [], []
    cur = 'input'
    n_layers = 2 + 2*num_conv + 1
    for i in range(n_layers):
        w = sd.get(f'body.{i}.weight')
        if w.ndim == 4:
            b = sd[f'body.{i}.bias']
            inits += [numpy_helper.from_array(w.astype(np.float32), f'w{i}'), numpy_helper.from_array(b.astype(np.float32), f'b{i}')]
            nodes.append(helper.make_node('Conv', [cur, f'w{i}', f'b{i}'], [f'x{i}'], pads=[1,1,1,1], kernel_shape=[3,3]))
        else:
            inits.append(numpy_helper.from_array(w.astype(np.float32).reshape(-1,1,1), f'w{i}'))
            nodes.append(helper.make_node('PRelu', [cur, f'w{i}'], [f'x{i}']))
        cur = f'x{i}'
    nodes.append(helper.make_node('DepthToSpace', [cur], ['ps'], blocksize=4, mode='CRD'))
    inits.append(numpy_helper.from_array(np.array([1,1,4,4], np.float32), 'scales'))
    nodes.append(helper.make_node('Resize', ['input', '', 'scales'], ['base'], mode='nearest', coordinate_transformation_mode='asymmetric', nearest_mode='floor'))
    nodes.append(helper.make_node('Add', ['ps', 'base'], ['output']))
    g = helper.make_graph(nodes, 'srvgg', [helper.make_tensor_value_info('input', TensorProto.FLOAT, [1,3,'h','w'])],
                          [helper.make_tensor_value_info('output', TensorProto.FLOAT, [1,3,'H','W'])], inits)
    m = helper.make_model(g, opset_imports=[helper.make_opsetid('', 13)], producer_name='realesrgan-convert')
    m.ir_version = 8
    onnx.checker.check_model(m)
    onnx.save(m, out)

build('realesr-general-x4v3.pth', 'realesr-general-x4v3.onnx', 32)
build('realesr-animevideov3.pth', 'realesr-animevideov3.onnx', 16)
