document.addEventListener('DOMContentLoaded', function() {
    // ... (seu código JavaScript existente para flash messages, dark mode, etc.)

    // Lógica para Alternar Modo Escuro/Claro (EXISTENTE - MANTIDO)
    const darkModeToggle = document.getElementById('dark-mode-toggle'); //
    const body = document.body; //

    const enableDarkMode = () => { //
        body.classList.add('dark-mode'); //
        localStorage.setItem('darkMode', 'enabled'); //
        if(darkModeToggle) darkModeToggle.textContent = 'Ativar Modo Claro'; //
    }

    const disableDarkMode = () => { //
        body.classList.remove('dark-mode'); //
        localStorage.setItem('darkMode', 'disabled'); //
        if(darkModeToggle) darkModeToggle.textContent = 'Ativar Modo Escuro'; //
    }

    if (localStorage.getItem('darkMode') === 'enabled') { //
        enableDarkMode(); //
    } else {
        disableDarkMode();  //
    }

    if (darkModeToggle) { //
        if (body.classList.contains('dark-mode')) { //
            darkModeToggle.textContent = 'Ativar Modo Claro'; //
        } else {
            darkModeToggle.textContent = 'Ativar Modo Escuro'; //
        }
        darkModeToggle.addEventListener('click', () => { //
            if (body.classList.contains('dark-mode')) { //
                disableDarkMode(); //
            } else {
                enableDarkMode(); //
            }
        });
    }
    
    // Formatação de input (EXISTENTE - MANTIDO)
    const expiryDateInput = document.getElementById('expiry_date'); //
    if (expiryDateInput) { //
        expiryDateInput.addEventListener('input', function(e) { //
            let value = e.target.value.replace(/\D/g, '');  //
            if (value.length > 2) { //
                value = value.substring(0, 2) + '/' + value.substring(2, 4); //
            }
            e.target.value = value; //
        });
    }
    // ... (outros formatadores de input existentes)


    // --- NOVO: SIMULADOR DE FINANCIAMENTO ---
    const simulateBtn = document.getElementById('simulateFinancingBtn');
    if (simulateBtn) {
        simulateBtn.addEventListener('click', function() {
            const vehiclePrice = parseFloat(document.getElementById('vehiclePrice').value.replace(',', '.'));
            const downPayment = parseFloat(document.getElementById('downPayment').value) || 0;
            const numInstallments = parseInt(document.getElementById('installments').value);
            const monthlyInterestRateUser = parseFloat(document.getElementById('interestRate').value); // ex: 1.5 para 1.5%
            const resultDiv = document.getElementById('financingResult');

            if (isNaN(vehiclePrice) || isNaN(monthlyInterestRateUser) || monthlyInterestRateUser <= 0) {
                resultDiv.textContent = 'Por favor, verifique os valores do veículo e da taxa de juros.';
                resultDiv.style.color = 'red';
                return;
            }
            if (downPayment >= vehiclePrice) {
                resultDiv.textContent = 'Entrada maior ou igual ao preço do veículo. Não há o que financiar.';
                resultDiv.style.color = 'green';
                return;
            }

            const loanAmount = vehiclePrice - downPayment;
            const monthlyRateDecimal = monthlyInterestRateUser / 100; // Converte 1.5% para 0.015

            let installmentValue;
            if (monthlyRateDecimal === 0) { // Juros zero
                 installmentValue = loanAmount / numInstallments;
            } else {
                // Fórmula da Tabela Price (Sistema Francês de Amortização)
                // P = L * [c(1+c)^n] / [(1+c)^n - 1]
                installmentValue = loanAmount * (monthlyRateDecimal * Math.pow(1 + monthlyRateDecimal, numInstallments)) / (Math.pow(1 + monthlyRateDecimal, numInstallments) - 1);
            }
            
            if (isFinite(installmentValue) && installmentValue > 0) {
                resultDiv.innerHTML = `Valor da Parcela: <strong>R$ ${installmentValue.toFixed(2).replace('.', ',')}</strong> (${numInstallments}x)`;
                resultDiv.style.color = 'var(--primary-color)';
            } else {
                resultDiv.textContent = 'Não foi possível calcular. Verifique os dados.';
                resultDiv.style.color = 'red';
            }
        });
    }

    // --- NOVO: LÓGICA BÁSICA DO CARROSSEL DE IMAGENS ---
    const carousel = document.querySelector('.carousel-container');
    if (carousel) {
        const slides = carousel.querySelectorAll('.carousel-slide');
        let currentSlide = 0;

        function showSlide(index) {
            slides.forEach((slide, i) => {
                slide.classList.remove('active');
                if (i === index) {
                    slide.classList.add('active');
                }
            });
        }

        window.changeSlide = function(n) { // Expor a função globalmente para onclick
            currentSlide += n;
            if (currentSlide >= slides.length) {
                currentSlide = 0;
            }
            if (currentSlide < 0) {
                currentSlide = slides.length - 1;
            }
            showSlide(currentSlide);
        }
        // Mostrar o primeiro slide inicialmente (já feito com a classe 'active' no HTML)
        // if (slides.length > 0) showSlide(0); // Desnecessário se o HTML já marca o primeiro como active
    }
});