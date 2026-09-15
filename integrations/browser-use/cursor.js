(() => {
  if (window.__lupaCursor) return;
  const install = () => {
    if (!document.documentElement || window.__lupaCursor) return;
    const cursor = document.createElement('div');
    cursor.setAttribute('aria-hidden', 'true');
    cursor.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;border:3px solid #ff477e;border-radius:50%;background:#ff477e33;pointer-events:none;z-index:2147483647;transform:translate(-50%,-50%);display:none';
    const move = e => { cursor.style.display = 'block'; cursor.style.left = e.clientX + 'px'; cursor.style.top = e.clientY + 'px'; };
    const click = () => cursor.animate([{scale:1}, {scale:2, opacity:.4}, {scale:1}], {duration:450});
    document.documentElement.append(cursor);
    document.addEventListener('mousemove', move, true);
    document.addEventListener('mousedown', click, true);
    window.__lupaCursor = () => {
      cursor.remove();
      document.removeEventListener('mousemove', move, true);
      document.removeEventListener('mousedown', click, true);
      delete window.__lupaCursor;
    };
  };
  if (document.documentElement) install();
  else document.addEventListener('DOMContentLoaded', install, {once:true});
})();
