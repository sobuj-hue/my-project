/* ═══════════════════════════════════════════════
   Axon AI — Shared JavaScript
   ═══════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ─── Mobile Nav Toggle ─── */
  const hamburger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobileMenu');

  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      hamburger.classList.toggle('open');
      mobileMenu.classList.toggle('open');
      document.body.style.overflow = mobileMenu.classList.contains('open') ? 'hidden' : '';
    });
    // Close on link click
    mobileMenu.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        hamburger.classList.remove('open');
        mobileMenu.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  /* ─── Fade-in on Scroll ─── */
  const fadeEls = document.querySelectorAll('.fade-up');
  if (fadeEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.08 });
    fadeEls.forEach(el => io.observe(el));
  }

  /* ─── Active Nav Link ─── */
  const currentPage = location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a, .mobile-menu a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === currentPage || (currentPage === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });

  /* ─── Pricing Toggle (monthly / annual) ─── */
  const toggle = document.getElementById('pricingToggle');
  if (toggle) {
    const monthlyLabel = document.getElementById('labelMonthly');
    const annualLabel = document.getElementById('labelAnnual');
    const monthlyPrices = document.querySelectorAll('.price-monthly');
    const annualPrices = document.querySelectorAll('.price-annual');

    let isAnnual = false;

    function updatePricing() {
      toggle.classList.toggle('on', isAnnual);
      monthlyLabel.classList.toggle('active-label', !isAnnual);
      annualLabel.classList.toggle('active-label', isAnnual);
      monthlyPrices.forEach(el => el.style.display = isAnnual ? 'none' : '');
      annualPrices.forEach(el => el.style.display = isAnnual ? '' : 'none');
    }

    toggle.addEventListener('click', () => { isAnnual = !isAnnual; updatePricing(); });
    updatePricing();
  }

  /* ─── FAQ Accordion ─── */
  document.querySelectorAll('.faq-q').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const wasOpen = item.classList.contains('open');
      // Close all first
      document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
      if (!wasOpen) item.classList.add('open');
    });
  });

  /* ─── Waitlist Form ─── */
  const waitlistForm = document.getElementById('waitlistForm');
  if (waitlistForm) {
    waitlistForm.addEventListener('submit', e => {
      e.preventDefault();

      const btn = waitlistForm.querySelector('.btn-submit');
      const btnText = btn.querySelector('.btn-text');
      const btnLoading = btn.querySelector('.btn-loading');

      const data = {
        name: waitlistForm.elements.name.value.trim(),
        email: waitlistForm.elements.email.value.trim(),
        company_size: waitlistForm.elements.company_size ? waitlistForm.elements.company_size.value : '',
        joined_at: new Date().toISOString(),
      };

      btnText.style.display = 'none';
      btnLoading.style.display = 'inline';
      btn.disabled = true;

      // Persist client-side
      const list = JSON.parse(localStorage.getItem('axon_waitlist') || '[]');
      list.push(data);
      localStorage.setItem('axon_waitlist', JSON.stringify(list));

      setTimeout(() => {
        waitlistForm.style.display = 'none';
        const success = document.getElementById('waitlistSuccess');
        success.classList.add('show');
        success.style.display = 'flex';
        success.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 800);
    });
  }

  /* ─── Contact Form ─── */
  const contactForm = document.getElementById('contactForm');
  if (contactForm) {
    contactForm.addEventListener('submit', e => {
      e.preventDefault();
      const btn = contactForm.querySelector('.btn');
      const original = btn.textContent;
      btn.textContent = 'Sending...';
      btn.disabled = true;

      // Persist client-side
      const msgs = JSON.parse(localStorage.getItem('axon_contact') || '[]');
      msgs.push({
        name: contactForm.elements.name.value.trim(),
        email: contactForm.elements.email.value.trim(),
        subject: contactForm.elements.subject.value,
        message: contactForm.elements.message.value.trim(),
        sent_at: new Date().toISOString(),
      });
      localStorage.setItem('axon_contact', JSON.stringify(msgs));

      setTimeout(() => {
        contactForm.reset();
        btn.textContent = 'Sent!';
        setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2000);
      }, 800);
    });
  }

})();
