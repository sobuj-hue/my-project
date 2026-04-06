// Waitlist form handler
function handleSubmit(e) {
  e.preventDefault();

  const form = document.getElementById('waitlistForm');
  const btn = form.querySelector('.btn-submit');
  const btnText = btn.querySelector('.btn-text');
  const btnLoading = btn.querySelector('.btn-loading');

  // Collect form data
  const data = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    company_size: form.company_size.value,
    joined_at: new Date().toISOString(),
  };

  // Simulate submission (replace with real API call)
  btnText.style.display = 'none';
  btnLoading.style.display = 'inline';
  btn.disabled = true;

  // Store in localStorage so entry persists client-side
  const waitlist = JSON.parse(localStorage.getItem('axon_waitlist') || '[]');
  waitlist.push(data);
  localStorage.setItem('axon_waitlist', JSON.stringify(waitlist));

  // Simulate network delay
  setTimeout(() => {
    form.style.display = 'none';
    document.getElementById('waitlistSuccess').style.display = 'flex';
    // Scroll into view
    document.getElementById('waitlistSuccess').scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 900);
}

// Smooth active nav highlighting
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.nav-links a');

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        navLinks.forEach((link) => {
          link.classList.toggle(
            'active',
            link.getAttribute('href') === `#${entry.target.id}`
          );
        });
      }
    });
  },
  { rootMargin: '-40% 0px -55% 0px' }
);

sections.forEach((s) => observer.observe(s));

// Fade-in on scroll
const fadeEls = document.querySelectorAll(
  '.step, .use-case-card, .testimonial, .pricing-card'
);

const fadeObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = entry.target.style.transform.replace(
          'translateY(20px)',
          'translateY(0)'
        );
        fadeObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.1 }
);

fadeEls.forEach((el) => {
  el.style.opacity = '0';
  el.style.transform += ' translateY(20px)';
  el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
  fadeObserver.observe(el);
});

// Nav active link style
const style = document.createElement('style');
style.textContent = `.nav-links a.active { color: #f4f4f5; }`;
document.head.appendChild(style);
