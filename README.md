# 💼 Master Resume Adaptation Studio

Este projeto foi desenvolvido para ajudar você, Kevin, a adaptar seu currículo de forma inteligente e personalizada para vagas de emprego específicas, além de auxiliar no preenchimento de formulários e na geração de cartas de apresentação.

A aplicação utiliza um arquivo central `master_resume.json` que contém todo o seu histórico profissional detalhado em dois idiomas (Português e Inglês), além de diferentes variações de bullet points (com foco em Gestão de Projetos, Operações, Growth, Marketing, CRM e IA). Ao inserir a descrição de uma vaga e selecionar o idioma desejado, a IA seleciona e reescreve os pontos para se alinharem perfeitamente à oportunidade.

---

## 🛠️ Como Instalar e Rodar

### 1. Pré-requisitos
Certifique-se de que possui o Python instalado (versão 3.10 ou superior). O seu sistema atual possui o Python 3.12.

### 2. Instalação das Dependências
Abra seu terminal na pasta do projeto e instale as dependências:
```bash
pip install -r requirements.txt
```

### 3. Configurar Chave de API do Gemini
A aplicação utiliza a API do Gemini. Para configurá-la:
1. Copie o arquivo `.env.example` para um novo arquivo chamado `.env`:
   ```bash
   copy .env.example .env
   ```
2. Abra o arquivo `.env` e cole sua chave de API do Gemini na linha:
   ```text
   GEMINI_API_KEY=sua_chave_aqui
   ```
   *Caso não tenha uma chave, você pode gerá-la gratuitamente no [Google AI Studio](https://aistudio.google.com/).*
   
*Observação: Caso não configure o arquivo `.env`, você também poderá digitar a chave de API diretamente na barra lateral da aplicação visual.*

### 4. Executar a Aplicação
Com as dependências instaladas e a chave configurada, rode:
```bash
streamlit run app.py
```
Uma página no seu navegador se abrirá automaticamente (geralmente em `http://localhost:8501`).

---

## 📦 Funcionalidades da Aplicação

### 🎯 Estúdio de Adaptação (Aba Principal)
1. Insira o **Nome da Empresa**, **Nome do Cargo** e cole a **Descrição da Vaga** completa.
2. Escolha o **Idioma de Saída** na barra lateral.
3. Clique em **Adaptar Currículo e Materiais 🚀**.
4. Visualize os resultados:
   - **Currículo Visual (HTML/PDF):** Veja uma prévia exata do currículo com visual premium e faça o download do arquivo HTML correspondente.
   - **Currículo Markdown:** Uma versão textual limpa ideal para copiar ou converter para outros formatos de texto.
   - **Carta de Apresentação:** Uma carta personalizada para a vaga baseada nas suas reais conquistas profissionais.
   - **Auxiliar de Formulários:** Sugestões de respostas para perguntas de processos seletivos baseadas nas suas experiências (ex: desafios operacionais, CRM, automação, etc.).

### 📝 Editor do Currículo Mestre (Segunda Aba)
- Você pode visualizar todas as informações e bullet points do seu currículo mestre.
- É possível fazer alterações diretas na caixa de texto JSON e salvar para atualizar o arquivo `master_resume.json` permanentemente.

---

## 🖨️ Como Exportar o Currículo em PDF com Visual Premium

Para manter a fidelidade do design profissional (tipografia Inter, espaçamento equilibrado, margens limpas, etc.) sem necessitar de dependências pesadas em seu computador:

1. Na aba **Currículo Visual (HTML/PDF)**, clique no botão **Baixar Currículo HTML**.
2. Abra o arquivo `.html` baixado em qualquer navegador web (Chrome, Edge, Firefox, etc.).
3. Pressione a tecla de atalho **Ctrl + P** (ou Cmd + P no Mac) para abrir o diálogo de impressão.
4. Defina o Destino como **Salvar como PDF**.
5. Nas configurações adicionais do diálogo de impressão:
   - **Margens:** Defina para *Padrão* ou *Nenhuma*.
   - **Cabeçalhos e rodapés:** *Desmarque* esta opção para evitar que a URL e datas apareçam nas bordas da página.
   - **Gráficos de plano de fundo:** *Marque* esta opção para garantir que os elementos visuais apareçam corretamente.
6. Clique em **Salvar**.
