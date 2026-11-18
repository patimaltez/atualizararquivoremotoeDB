# Atualização do banco SQL Server

Automação em Python que baixa um arquivo de backup `.bak` de um servidor remoto usando SFTP e restaura esse backup no SQL Server. 
Em caso de falha, a rotina tenta enviar uma notificação por e-mail.

## O que o projeto faz

1. Conecta ao servidor remoto por SFTP e baixa o arquivo `.bak`.
2. Compara o tamanho do arquivo baixado com o tamanho informado pelo servidor.
3. Substitui o arquivo `.bak` local pelo arquivo baixado após a validação.
4. Restaura o banco configurado no SQL Server usando o backup.
5. Verifica se o banco restaurado está online e em modo multiusuário.
6. Registra as etapas em um arquivo de log.
7. Em caso de erro, tenta enviar um e-mail com os detalhes e o caminho do log.

## Pré-requisitos

- Windows com Python instalado.
- Acesso de rede ao servidor SFTP e ao SQL Server.
- Permissão para ler o arquivo remoto e gravá-lo no destino local.
- Microsoft ODBC Driver 17 for SQL Server instalado, ou outro driver configurado.
- Google Chrome instalado. Ele é utilizado para acessar o webmail e enviar notificações de erro.

## Instalação das dependências

Na pasta do projeto, execute:

```bash
pip install paramiko pyodbc python-dotenv selenium webdriver-manager
```

A instalação do pacote `pyodbc` não instala o driver Microsoft ODBC. 
Instale o driver correspondente separadamente, 
se ainda não estiver disponível no computador.

## Configuração

O script procura o arquivo `.env` neste caminho:

```text
M:\Business Intelligence\SCRIPTS PYTHON\.env
```

Crie ou atualize esse arquivo com as configurações abaixo:

```env
AHREAS_SFTP_HOST=servidor_sftp
AHREAS_SFTP_PORT=22
AHREAS_SFTP_USER=usuario_sftp
AHREAS_SFTP_PASSWORD=senha_sftp
AHREAS_REMOTE_BAK=/caminho/remoto/arquivo.bak
AHREAS_LOCAL_BAK=C:\caminho\local\arquivo.bak

SQL_SERVER_HOST=servidor_sql
SQL_SERVER_DRIVER=ODBC Driver 17 for SQL Server
SQL_SERVER_USER=usuario_sql
SQL_SERVER_PASSWORD=senha_sql
AHREAS_DATABASE=SIGADM

WEBMAIL_URL=https://endereco-do-webmail
WEBMAIL_USER=usuario_webmail
WEBMAIL_PASSWORD=senha_webmail
WEBMAIL_DESTINATARIOS_AHREAS=destinatario@empresa.com
```

A porta SFTP é opcional e, se não for informada, será usada a porta `22`. O nome do banco é opcional e, se não for informado, será usado `SIGADM`.

Se `SQL_SERVER_USER` e `SQL_SERVER_PASSWORD` ficarem vazios ou não forem definidos, a conexão tentará usar a autenticação integrada do Windows.

As variáveis de webmail e destinatários são usadas para a notificação de erro. 
O caminho do arquivo `.env` e a pasta dos logs estão definidos no código; 
altere-os no arquivo `atualizar_bd_ahreas.py` caso sua estrutura seja diferente.

## Como executar

Abra o PowerShell, acesse a pasta do projeto e execute:

```powershell
cd "M:\Business Intelligence\SCRIPTS PYTHON\AtualizarBDAHREAS"
python atualizar_bd_ahreas.py
```

A execução pode levar vários minutos, dependendo do tamanho do arquivo `.bak`, da conexão de rede e do tempo de restauração do banco.

## Logs

Os logs são salvos na pasta `logs`, dentro da pasta do projeto. O arquivo é criado com a data da execução e registra as etapas da rotina e eventuais erros.

## Atenção antes de executar

**A restauração substitui o banco configurado pelo conteúdo do arquivo `.bak`.** O script executa a restauração com a opção `WITH REPLACE`, 
coloca o banco em modo de usuário único e desconecta as sessões existentes antes da substituição.

Antes de executar:

- Confirme que `AHREAS_DATABASE` aponta para o banco correto.
- Confirme que o arquivo remoto é o backup esperado.
- Faça e valide um backup do banco atual antes da restauração.
- Avise os usuários e serviços que possam estar conectados ao banco.
- Teste o procedimento em um ambiente não produtivo, se possível.
- Confirme que a conta SQL usada tem as permissões necessárias para restaurar o banco.

A execução incorreta pode sobrescrever dados existentes e interromper conexões com o banco.
