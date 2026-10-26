// Saving files: through the Android app's bridge into Downloads, or a normal
// browser download when running in a desktop browser.
export async function saveBlob(blob, name) {
  if (window.AndroidSave) return window.AndroidSave(blob, name);
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
  return '';
}
