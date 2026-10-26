// Loaded by both the AI Studio and the StykAnimate editor inside the Android app.
// Routes file downloads to the native side (WebView can't save blob: links) and
// keeps the editor's offline service worker out of the app, which ships its files.
(function () {
  var native = window.Android;
  if (!native) return;

  function toBase64(blob) {
    return new Promise(function (resolve, reject) {
      var r = new FileReader();
      r.onload = function () { resolve(String(r.result).split(',')[1] || ''); };
      r.onerror = function () { reject(r.error); };
      r.readAsDataURL(blob);
    });
  }

  /** Save a Blob to Downloads. Resolves with where it went. */
  window.AndroidSave = async function (blob, name) {
    var token = native.saveBegin(name, blob.type || 'application/octet-stream');
    if (String(token).indexOf('ERR:') === 0) throw new Error(String(token).slice(4));
    var CHUNK = 768 * 1024; // multiple of 3 so base64 pieces concatenate cleanly
    for (var off = 0; off < blob.size; off += CHUNK) {
      var ok = native.saveChunk(token, await toBase64(blob.slice(off, off + CHUNK)));
      if (!ok) throw new Error('Writing the file failed.');
    }
    var where = native.saveEnd(token);
    if (String(where).indexOf('ERR:') === 0) throw new Error(String(where).slice(4));
    return where;
  };

  function toast(text) {
    var el = document.createElement('div');
    el.textContent = text;
    el.style.cssText = 'position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#2b3240;color:#fff;padding:10px 16px;border-radius:12px;z-index:2147483647;font:14px system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.4);max-width:90vw';
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 3500);
  }

  var click = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function () {
    var href = this.href || '';
    if (this.hasAttribute('download') && (href.indexOf('blob:') === 0 || href.indexOf('data:') === 0)) {
      var name = this.getAttribute('download') || 'download';
      fetch(href).then(function (r) { return r.blob(); })
        .then(function (b) { return window.AndroidSave(b, name); })
        .then(function (where) { toast('Saved ' + name + (where ? ' to ' + where : '')); })
        .catch(function (e) { toast('Could not save ' + name + ': ' + (e && e.message || e)); });
      return;
    }
    return click.call(this);
  };

  if (navigator.serviceWorker) {
    navigator.serviceWorker.register = function () { return Promise.reject(new Error('Offline worker not needed in the Android app.')); };
  }
})();
