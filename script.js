// Ryan Phelan - site interactions

// Hero flip: the subject changes; the sentence holds. Settles on "The market sees" and stops.
(function () {
  var flip = document.getElementById('flip');
  if (!flip) return;
  var words = [
    'Your customers see',
    'Your salespeople see',
    'Your board sees',
    'Your analysts see',
    'Your exec team sees',
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

// Cookie consent - Google Consent Mode v2
(function () {
  var KEY = 'sg_consent';
  var GRANTED = {ad_storage:'granted',ad_user_data:'granted',ad_personalization:'granted',analytics_storage:'granted',functionality_storage:'granted',personalization_storage:'granted'};
  var DENIED  = {ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied',functionality_storage:'denied',personalization_storage:'denied'};

  function saved(){ try{ return JSON.parse(localStorage.getItem(KEY)); }catch(e){ return null; } }
  function gtagSafe(){ if(typeof gtag==='function'){ gtag.apply(null, arguments); } else { (window.dataLayer=window.dataLayer||[]).push(arguments); } }

  function apply(choice){
    var state = choice === 'accepted' ? GRANTED : DENIED;
    gtagSafe('consent','update',state);
    try{ localStorage.setItem(KEY, JSON.stringify({choice:choice, state:state})); }catch(e){}
  }

  var banner;
  function build(){
    if(banner) return;
    banner = document.createElement('div');
    banner.className = 'cc-banner';
    banner.setAttribute('role','dialog');
    banner.setAttribute('aria-label','Cookie consent');
    banner.innerHTML =
      '<div class="cc-inner">' +
        '<p class="cc-text">I use Google Analytics to see how visitors use this site. Nothing loads until you choose, and you can change your mind anytime under “Cookie settings” in the footer.</p>' +
        '<div class="cc-actions">' +
          '<button class="cc-btn cc-decline" type="button">Decline</button>' +
          '<button class="cc-btn cc-accept" type="button">Accept</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(banner);
    banner.querySelector('.cc-accept').addEventListener('click', function(){ apply('accepted'); hide(); });
    banner.querySelector('.cc-decline').addEventListener('click', function(){ apply('declined'); hide(); });
  }
  function show(){ build(); requestAnimationFrame(function(){ banner.classList.add('show'); }); }
  function hide(){ if(banner){ banner.classList.remove('show'); } }

  // "Cookie settings" reopen link in the footer
  function wireReopen(){
    var links = document.querySelector('.flinks');
    if(!links) return;
    var a = document.createElement('a');
    a.href = '#'; a.textContent = 'Cookie settings'; a.className = 'cc-reopen';
    a.addEventListener('click', function(e){ e.preventDefault(); show(); });
    links.appendChild(a);
  }

  document.addEventListener('DOMContentLoaded', function(){
    wireReopen();
    if(!saved()){ show(); }   // no choice on record yet - ask
  });
})();
