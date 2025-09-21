function highlightText(text, clu){
  if(!text) return "";
  let html = esc(text);
  (clu||[]).forEach(h=>{
    const t = esc(h.family.toLowerCase());
    html = html.replace(new RegExp(`(${t})`,"gi"), `<mark>$1</mark>`);
  });
  return `<div style="white-space:pre-wrap">${html}</div>`;
}
function esc(s){return s.replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));}