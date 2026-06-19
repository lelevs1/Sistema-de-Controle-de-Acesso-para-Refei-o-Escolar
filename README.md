# SysMerenda (Sistema de Controle de Acesso para Refeição Escolar) - Backend

## 📖 Visão Geral do Projeto e Contextualização do Problema

O **SysMerenda (Sistema de Controle de Acesso para Refeição Escolar)**  foi idealizado para modernizar e organizar o fluxo de distribuição de refeições em instituições de ensino. O processo manual ou desintegrado de controle de cantinas frequentemente gera filas, dificulta a auditoria de gastos e abre margens para inconsistências, como o registro duplicado de refeições no mesmo dia.

Este projeto resolve essa dor centralizando a liberação de almoços por meio de verificação biométrica e manual, garantindo segurança, agilidade na fila da cantina e total transparência financeira para os órgãos de fiscalização escolar.

## 🎯 Objetivos da Solução Desenvolvida

* **Controle Rigoroso de Acesso:** Garantir que cada estudante consuma apenas uma refeição por dia, bloqueando tentativas duplicadas ou de alunos inativos.


* **Gestão de Papéis e Permissões:** Prover interfaces e acessos específicos baseados na função do usuário, incluindo Administrador, Fiscal, Gestor, Empresa e Operador da cantina.


* **Monitoramento em Tempo Real:** Fornecer feedback instantâneo para a interface do operador no momento da leitura da digital utilizando WebSockets.


* **Transparência e Auditoria:** Gerar relatórios detalhados em PDF e CSV e permitir a validação fiscal de períodos fechados, gerando protocolos únicos e imutáveis.


* **Flexibilidade:** Permitir a importação em lote de estudantes via arquivos CSV/Excel e fácil configuração de horários de funcionamento e valores de refeição.



## 🛠️ Tecnologias Utilizadas

A API foi construída utilizando as melhores práticas do ecossistema Python, focando em escalabilidade e processamento assíncrono:

* **Linguagem:** Python 3.14.0.


* **Framework Web:** Django 5.2.8 com Django REST Framework  para construção robusta da API.


* **Comunicação em Tempo Real:** Django Channels e Uvicorn (ASGI) para suporte a WebSockets.


* **Banco de Dados:** SQLite3 para desenvolvimento local, com suporte a PostgreSQL via `dj_database_url` para produção.


* **Autenticação e Segurança:** JWT (JSON Web Tokens) via `rest_framework_simplejwt` e integração OAuth2 com Google para acesso seguro de Fiscais.


* **Armazenamento de Mídia:** Cloudinary API para gestão de fotos de estudantes na nuvem.


* **Geração de Relatórios:** Biblioteca `ReportLab` para exportação nativa de PDFs.



## ⚙️ Instruções para Instalação, Configuração e Execução

### Pré-requisitos

* Python 3.14+ instalado na máquina.
* Git para clonagem do repositório.

### Passo a Passo

1. **Clonar o repositório:**

```bash
git clone https://github.com/lelevs1/Sistema-de-Controle-de-Acesso-para-Refei-o-Escolar.git
cd Sistema-de-Controle-de-Acesso-para-Refei-o-Escolar/IFB/projeto_IFB

```

2. **Criar e ativar o ambiente virtual:**

```bash
python -m venv .venv
# No Windows (PowerShell):
.\.venv\Scripts\activate
# No Linux/Mac:
source .venv/bin/activate

```

3. **Instalar as dependências:**

```bash
pip install -r requirements.txt

```

4. **Configurar as Variáveis de Ambiente:**
Crie um arquivo `.env` na pasta `projeto_IFB` (onde fica o `settings.py`) contendo as chaves necessárias, como `SECRET_KEY`, e as credenciais do Cloudinary e Google OAuth.


5. **Aplicar as Migrações do Banco de Dados:**

```bash
python manage.py migrate

```

6. **Popular o Banco de Dados (Dados Iniciais):**
Execute os scripts para inserir os Cursos e Turmas iniciais:

```bash
python populate_cursos.py
python populate_turmas.py

```

7. **Criar um Superusuário (Admin):**

```bash
python manage.py createsuperuser

```

8. **Executar o Servidor (com suporte a WebSockets):**

```bash
uvicorn setup.asgi:application --reload

```

O servidor estará rodando em `http://127.0.0.1:8000/`.

## 🧠 Principais Decisões Técnicas Adotadas pela Equipe

* **Uso de WebSockets (Django Channels):** Para evitar que o Frontend faça requisições pesadas e contínuas (Long Polling) perguntando se um aluno passou a digital, implementamos o padrão WebSocket (ASGI). Assim que uma digital é validada na catraca, o backend "empurra" ativamente a liberação para a tela do operador em milissegundos.


* **Autenticação Híbrida (JWT + Google OAuth):** Decidimos utilizar tokens JWT para a comunicação padrão da API com o front-end , mas implementamos obrigatoriamente o login via Google para a função de "Fiscal", garantindo um nível extra de segurança e rastreabilidade para os usuários que auditam os pagamentos.


* **Separação do Modelo de Usuário (`AbstractBaseUser`):** Optamos por sobrescrever o usuário padrão do Django para criar um modelo focado em `email` e com um sistema de `papel` (RBAC - Role-Based Access Control) nativo. Isso facilitou imensamente a criação de rotas protegidas (ex: `@permission_classes([IsAdminOrFiscal])`).


* **Armazenamento em Nuvem (Cloudinary):** Para evitar a sobrecarga do servidor local com imagens estáticas, centralizamos o upload de fotos dos estudantes no Cloudinary, o que também facilita futuras migrações de infraestrutura (deploy no Render, Heroku, etc).



## 👥 Integrantes da Equipe

* **[Natália Martins](https://github.com/nataliamartinsux)** - Desenvolvedora Full-Stack / Frontend / Backend
* **[Letícia Vieira](https://github.com/lelevs1)** - Desenvolvedora Backend
