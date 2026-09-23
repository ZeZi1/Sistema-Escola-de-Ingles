# 🏫 Sistema de Gestão Escolar (School Management System)

Um sistema completo de gestão escolar desenvolvido em **Python (Flask)** e **SQLite**. Este projeto foi criado para digitalizar e automatizar o controlo de turmas, diários de classe, notas e a comunicação entre a escola e os pais/responsáveis.

## 🚀 Funcionalidades Principais

* **Controlo de Acessos (Role-based Access):** Três tipos de painéis isolados e seguros para Administradores, Professores e Pais.
* **Gestão Inteligente de Turmas e Alunos:** Matrículas em massa com geração automática e padronizada de logins para os responsáveis, evitando conflitos e duplicidades no banco de dados.
* **Diário de Classe Digital:** Área exclusiva para o professor registar presenças, notas, tarefas (homework) e o tema de cada aula, tudo agrupado cronologicamente.
* **Ferramenta "Raio-X" (Manutenção de DB):** Um painel de manutenção isolado e protegido por senha independente, criado para corrigir problemas de integridade relacional, remover perfis fantasmas (*orphaned records*) e resolver conflitos de sufixos de login gerados por nomes homónimos.
* **Exportação de Dados:** Geração automatizada de relatórios gerais de rendimento em formato CSV.

## 🛠️ Tecnologias e Bibliotecas Utilizadas

* **Backend:** Python 3, Flask
* **Autenticação:** Flask-Login, Werkzeug (Security & Password Hashing)
* **Banco de Dados:** SQLite (com Foreign Keys e Queries otimizadas)
* **Frontend:** HTML5, CSS3, JavaScript (Vanilla), manipulação de DOM e Fetch API para requisições assíncronas.

## 🔒 Privacidade e Segurança

Para proteger dados reais de alunos e professores, **o banco de dados de produção e as chaves secretas não estão incluídos neste repositório.** As senhas no código-fonte foram substituídas por variáveis de ambiente ou *placeholders*. O sistema conta com um script de inicialização que gera a estrutura de tabelas e o utilizador Administrador padrão automaticamente ao ser executado pela primeira vez.
