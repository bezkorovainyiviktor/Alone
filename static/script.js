// ============= Canvas Background Animation =============
const canvas = document.getElementById('canvas');
if (canvas) {
    const ctx = canvas.getContext('2d');

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const particles = [];
    const particleCount = 50;

    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 0.5;
            this.vy = (Math.random() - 0.5) * 0.5;
            this.radius = Math.random() * 2 + 1;
            this.opacity = Math.random() * 0.5 + 0.2;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;

            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }

        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 107, 107, ${this.opacity})`;
            ctx.fill();
        }
    }

    // Initialize particles
    for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < 150) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(78, 205, 196, ${0.2 * (1 - distance / 150)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }
    }

    function animateBackground() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(particle => {
            particle.update();
            particle.draw();
        });

        drawConnections();
        requestAnimationFrame(animateBackground);
    }

    animateBackground();
}

// ============= Stats Animation =============
function animateStats() {
    const statCards = document.querySelectorAll('.stat-number');
    if (statCards.length === 0) return;

    statCards.forEach((card) => {
        const target = parseInt(card.dataset.target);
        let current = 0;

        const interval = setInterval(() => {
            const increment = target / 50;
            current += increment;

            if (current >= target) {
                current = target;
                clearInterval(interval);
            }

            const isPercentage = card.textContent.includes('%');
            card.textContent = isPercentage
                ? current.toFixed(1) + '%'
                : Math.round(current);
        }, 30);
    });
}

// Trigger stats animation when section comes into view
const statsSection = document.getElementById('stats');
if (statsSection) {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.animated) {
                animateStats();
                entry.target.animated = true;
            }
        });
    });

    observer.observe(statsSection);
}

// ============= Smooth Scroll =============
function scrollToSection(id) {
    const element = document.getElementById(id);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

// ============= Form Submissions =============
const contactForm = document.getElementById('contactForm');
if (contactForm) {
    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const button = e.target.querySelector('button');
        const originalText = button.innerHTML;

        button.innerHTML = '<span>Надсилання...</span>';
        button.disabled = true;

        try {
            const response = await fetch('/api/message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            button.innerHTML = '<span>✓ Успішно!</span>';
            e.target.reset();

            setTimeout(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            }, 3000);
        } catch (error) {
            button.innerHTML = originalText;
            button.disabled = false;
            alert('Помилка при надсиланні!');
        }
    });
}



// ============= Page Load Animation =============
window.addEventListener('load', () => {
    document.body.style.opacity = '1';
});
