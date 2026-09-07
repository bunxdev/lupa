() => {
  const el=s=>document.querySelector(s);
  let canvas=false;try{canvas=!!el('canvas').getContext('2d')}catch{}
  return {title:document.title,js:el('#ready').textContent==='JavaScript OK',fetch:el('#data').textContent==='Fetch OK',cards:document.querySelectorAll('.card').length,cookie:document.cookie.includes('comparison=ok'),greeting:el('#greeting').textContent,canvas,audioContext:typeof AudioContext!=='undefined',videoMP4:!!document.createElement('video').canPlayType?.('video/mp4')};
}
