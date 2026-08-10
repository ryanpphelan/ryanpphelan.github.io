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

// Article share row: LinkedIn, X, Facebook (injected on any page with an article body)
(function () {
  var body = document.querySelector('.art-body');
  if (!body) return;
  var pageUrl = location.origin + location.pathname; // share the ryanphelan.com page, not the canonical
  var u = encodeURIComponent(pageUrl);
  var t = encodeURIComponent(document.title.replace(/\s*[|·]\s*Ryan Phelan\s*$/, ''));
  var ICON = {
    li: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 11-.02 5 2.5 2.5 0 01.02-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-.95 1.83-1.95 3.77-1.95 4.03 0 4.78 2.5 4.78 5.75V21h-4v-5.4c0-1.29-.02-2.95-1.8-2.95-1.8 0-2.07 1.4-2.07 2.85V21H9z"/></svg>',
    x:  '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M18.9 2H22l-7.1 8.1L23 22h-6.6l-5.2-6.8L5.3 22H2.2l7.6-8.7L1.7 2h6.7l4.7 6.2zM17.8 20h1.7L7.3 3.9H5.5z"/></svg>',
    fb: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M22 12a10 10 0 10-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.78-3.89 1.09 0 2.24.2 2.24.2v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.78l-.44 2.89h-2.34v6.99A10 10 0 0022 12z"/></svg>'
  };
  var links = [
    ['Share on LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' + u, ICON.li],
    ['Share on X', 'https://twitter.com/intent/tweet?url=' + u + '&text=' + t, ICON.x],
    ['Share on Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + u, ICON.fb]
  ];
  var row = document.createElement('div');
  row.className = 'art-share';
  row.innerHTML = '<span class="art-share-label">Share</span>' + links.map(function (l) {
    return '<a class="art-share-btn" href="' + l[1] + '" target="_blank" rel="noopener" aria-label="' + l[0] + '">' + l[2] + '</a>';
  }).join('');
  body.parentNode.appendChild(row);
})();
