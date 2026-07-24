// Ryan Phelan — site interactions

// Hero flip: the subject changes; the sentence holds. Settles on "The market sees" and stops.
(function () {
  var flip = document.getElementById('flip');
  if (!flip) return;
  var words = [
    'Your customers see',
    'Your salespeople see',
    'Your board sees',
    'Your analysts see',
    'The market sees'
  ];
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce) return; // leave the real, static first sentence in place
  var i = 0;
  function step() {
    i++;
    if (i >= words.length) return; // rest on the final word
    flip.classList.add('fade');
    setTimeout(function () {
      flip.textContent = words[i];
      flip.classList.remove('fade');
      if (i < words.length - 1) setTimeout(step, 1750);
    }, 500);
  }
  setTimeout(step, 1600);
})();

// Mobile nav
(function () {
  var t = document.querySelector('.nav-toggle');
  var l = document.getElementById('navlinks');
  if (!t || !l) return;
  t.addEventListener('click', function () {
    var open = l.classList.toggle('open');
    t.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
})();
