document.addEventListener('DOMContentLoaded', function() {
    console.log('=== CATALOG LOADED ===');
    let currentType = 'cats';

    // Pet type buttons
    const typeButtons = document.querySelectorAll('.type-btn');
    console.log('Found type buttons:', typeButtons.length);
    
    typeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            console.log('Clicked type button:', e.target.dataset.type);
            document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentType = e.target.dataset.type;
            loadPets();
        });
    });

    // Filter inputs
    const breed = document.getElementById('breed');
    const gender = document.getElementById('gender');
    const age = document.getElementById('age');
    const color = document.getElementById('color');
    const sort = document.getElementById('sort');
    
    // Debounce function to limit API calls while typing
    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    const debouncedLoadPets = debounce(loadPets);
    
    if (breed) breed.addEventListener('input', debouncedLoadPets);
    if (gender) gender.addEventListener('change', loadPets);
    if (age) age.addEventListener('change', loadPets);
    if (color) color.addEventListener('input', debouncedLoadPets);
    if (sort) sort.addEventListener('change', loadPets);

    async function loadPets() {
        try {
            console.log('Loading pets for type:', currentType);
            
            const breedVal = document.getElementById('breed')?.value || '';
            const genderVal = document.getElementById('gender')?.value || '';
            const ageVal = document.getElementById('age')?.value || '';
            const colorVal = document.getElementById('color')?.value || '';
            const sortVal = document.getElementById('sort')?.value || 'name';

            const params = new URLSearchParams({
                type: currentType,
                breed: breedVal,
                gender: genderVal,
                age: ageVal,
                color: colorVal,
                sort: sortVal
            });

            const url = `/api/pets?${params}`;
            console.log('Fetching:', url);
            
            const response = await fetch(url);
            console.log('Response status:', response.status);
            
            const pets = await response.json();
            console.log('Received pets:', pets.length, 'items');

            const grid = document.getElementById('petsGrid');
            if (!grid) {
                console.error('Grid not found!');
                return;
            }
            
            grid.innerHTML = '';

            if (!pets || pets.length === 0) {
                console.log('No pets returned');
                grid.innerHTML = '<div class="no-pets">😢 На жаль, нема результатів за твоїми критеріями...</div>';
                return;
            }

            pets.forEach(pet => {
                const card = document.createElement('div');
                card.className = 'pet-card';
                card.innerHTML = `
                    <div class="pet-image-card">
                        <img src="${pet.image_url}" alt="${pet.name}" class="pet-photo" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><rect fill=%22%23667eea%22 width=%22200%22 height=%22200%22/><text x=%2250%25%22 y=%2250%25%22 font-size=%2248%22 dominant-baseline=%22middle%22 text-anchor=%22middle%22 fill=%22white%22>${pet.emoji}</text></svg>'">
                    </div>
                    <h3 class="pet-name">${pet.name}</h3>
                    <p class="pet-breed">${pet.breed}</p>
                    <div class="pet-info">
                        <span class="pet-age">🎂 ${pet.age} років</span>
                        <span class="pet-gender">${pet.gender === 'М' ? '♂️ Хлопчик' : '♀️ Дівчинка'}</span>
                    </div>
                    <p class="pet-color">🎨 ${pet.color}</p>
                    <p class="pet-description">${pet.description}</p>
                    <div class="pet-price">₴ ${pet.price.toLocaleString('uk-UA')}</div>
                    <a href="/pet/${currentType}/${pet.id}" class="btn btn-primary full-width">
                        Деталі & Замовити
                    </a>
                `;
                grid.appendChild(card);
            });
            console.log('Rendered', pets.length, 'cards');
        } catch (error) {
            console.error('Error loading pets:', error);
        }
    }

    function resetFilters() {
        document.getElementById('breed').value = '';
        document.getElementById('gender').value = '';
        document.getElementById('age').value = '';
        document.getElementById('color').value = '';
        document.getElementById('sort').value = 'name';
        loadPets();
    }

    // Expose resetFilters to global scope for onclick handler
    window.resetFilters = resetFilters;

    // Load initial pets
    console.log('Loading initial pets...');
    loadPets();
});
