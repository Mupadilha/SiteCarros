// static/js/model_loader.js
function setupModelFetching(brandSelectId, modelSelectId, initialSelectedModel, modelApiUrlTemplate) {
    const brandSelect = document.getElementById(brandSelectId);
    const modelSelect = document.getElementById(modelSelectId);

    function fetchModels(brandName, selectedModelValue) {
        if (brandName) {
            modelSelect.disabled = true;
            modelSelect.innerHTML = '<option value="">Carregando modelos...</option>';
            
            const apiUrl = modelApiUrlTemplate.replace('__BRAND__', encodeURIComponent(brandName));

            fetch(apiUrl)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    modelSelect.innerHTML = '<option value="">-- Selecione um Modelo --</option>';
                    if (data.models && data.models.length > 0) {
                        data.models.forEach(model => {
                            const option = document.createElement('option');
                            option.value = model;
                            option.textContent = model;
                            if (model === selectedModelValue) {
                                option.selected = true;
                            }
                            modelSelect.appendChild(option);
                        });
                    } else {
                        modelSelect.innerHTML = '<option value="">-- Nenhum modelo encontrado --</option>';
                    }
                    modelSelect.disabled = false;
                })
                .catch(error => {
                    console.error('Erro ao buscar modelos:', error);
                    modelSelect.innerHTML = '<option value="">-- Erro ao carregar modelos --</option>';
                    modelSelect.disabled = true; 
                });
        } else {
            modelSelect.innerHTML = '<option value="">-- Selecione uma Marca Primeiro --</option>';
            modelSelect.disabled = true;
        }
    }

    if (brandSelect) {
        brandSelect.addEventListener('change', function() {
            fetchModels(this.value, null); 
        });

        // População inicial dos modelos se uma marca já estiver selecionada
        if (brandSelect.value) {
            fetchModels(brandSelect.value, initialSelectedModel);
        } else {
            modelSelect.disabled = true;
        }
    }
}