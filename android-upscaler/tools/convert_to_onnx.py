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

class Graph:
    def __init__(self, sd):
        self.sd, self.nodes, self.inits, self.n = sd, [], [], 0

    def tmp(self):
        self.n += 1
        return f't{self.n}'

    def const(self, arr):
        name = self.tmp()
        self.inits.append(numpy_helper.from_array(np.asarray(arr, np.float32), name))
        return name

    def op(self, typ, inputs, **attrs):
        out = self.tmp()
        self.nodes.append(helper.make_node(typ, inputs, [out], **attrs))
        return out

    def conv(self, x, key):
        w, b = self.sd[key + '.weight'], self.sd[key + '.bias']
        return self.op('Conv', [x, self.const(w), self.const(b)], pads=[1, 1, 1, 1], kernel_shape=[3, 3])

    def upsample_nearest(self, x, s):
        return self.op('Resize', [x, '', self.const([1, 1, s, s])], mode='nearest',
                       coordinate_transformation_mode='asymmetric', nearest_mode='floor')

    def save(self, out_name, path):
        self.nodes[-1].output[0] = 'output'
        g = helper.make_graph(self.nodes, 'realesrgan',
                              [helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 3, 'h', 'w'])],
                              [helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 3, 'H', 'W'])],
                              self.inits)
        m = helper.make_model(g, opset_imports=[helper.make_opsetid('', 13)], producer_name='realesrgan-convert')
        m.ir_version = 8
        onnx.checker.check_model(m)
        onnx.save(m, path)


def weights(pth):
    sd = load_pth(pth)
    return sd.get('params_ema', sd.get('params', sd))


def build_srvgg(pth, out, num_conv):
    """SRVGGNetCompact (realesrgan/archs/srvgg_arch.py), upscale 4, PReLU."""
    sd = weights(pth)
    g = Graph(sd)
    x = 'input'
    for i in range(2 + 2 * num_conv + 1):
        w = sd[f'body.{i}.weight']
        if w.ndim == 4:
            x = g.conv(x, f'body.{i}')
        else:
            x = g.op('PRelu', [x, g.const(w.reshape(-1, 1, 1))])
    x = g.op('DepthToSpace', [x], blocksize=4, mode='CRD')
    g.op('Add', [x, g.upsample_nearest('input', 4)])
    g.save('output', out)


def build_rrdb(pth, out, num_block=23):
    """RRDBNet (basicsr/archs/rrdbnet_arch.py), scale 4, as used by RealESRGAN_x4plus."""
    g = Graph(weights(pth))
    lrelu = lambda t: g.op('LeakyRelu', [t], alpha=0.2)
    point2 = g.const(0.2)

    def rdb(x, key):
        feats = [x]
        for i in range(1, 5):
            inp = feats[0] if len(feats) == 1 else g.op('Concat', feats, axis=1)
            feats.append(lrelu(g.conv(inp, f'{key}.conv{i}')))
        x5 = g.conv(g.op('Concat', feats, axis=1), f'{key}.conv5')
        return g.op('Add', [g.op('Mul', [x5, point2]), x])

    feat = g.conv('input', 'conv_first')
    body = feat
    for b in range(num_block):
        out_b = body
        for r in (1, 2, 3):
            out_b = rdb(out_b, f'body.{b}.rdb{r}')
        body = g.op('Add', [g.op('Mul', [out_b, point2]), body])
    feat = g.op('Add', [feat, g.conv(body, 'conv_body')])
    feat = lrelu(g.conv(g.upsample_nearest(feat, 2), 'conv_up1'))
    feat = lrelu(g.conv(g.upsample_nearest(feat, 2), 'conv_up2'))
    g.conv(lrelu(g.conv(feat, 'conv_hr')), 'conv_last')
    g.save('output', out)


if __name__ == '__main__':
    import os
    if os.path.exists('realesr-general-x4v3.pth'):
        build_srvgg('realesr-general-x4v3.pth', 'realesr-general-x4v3.onnx', 32)
    if os.path.exists('realesr-animevideov3.pth'):
        build_srvgg('realesr-animevideov3.pth', 'realesr-animevideov3.onnx', 16)
    if os.path.exists('RealESRGAN_x4plus.pth'):
        build_rrdb('RealESRGAN_x4plus.pth', 'RealESRGAN_x4plus.onnx')
