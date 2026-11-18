# "M:\Business Intelligence\SCRIPTS PYTHON\AtualizarBDAHREAS\atualizar_bd_ahreas.py"

import os
import time
import logging
from pathlib import Path
from datetime import datetime

import paramiko
import pyodbc
from dotenv import load_dotenv

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
# executado em 03/11/2026 demora 40 minutos

# =====================================================================================
# CONFIGURAÇÕES
# =====================================================================================

CAMINHO_ENV = r"M:\Business Intelligence\SCRIPTS PYTHON\.env"
PROJECT_DIR = Path(r"M:\Business Intelligence\SCRIPTS PYTHON\AtualizarBDAHREAS")
LOG_DIR = PROJECT_DIR / "logs"


# =====================================================================================
# LOG
# =====================================================================================

def configurar_log() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_path = LOG_DIR / f"atualizar_bd_ahreas_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ],
    )

    return log_path


def log(msg: str) -> None:
    logging.info(msg)


# =====================================================================================
# .ENV
# =====================================================================================

def carregar_env() -> dict:
    if not Path(CAMINHO_ENV).exists():
        raise FileNotFoundError(f"Arquivo .env nao encontrado: {CAMINHO_ENV}")

    load_dotenv(CAMINHO_ENV, override=True)

    config = {
        "sftp_host": os.getenv("AHREAS_SFTP_HOST"),
        "sftp_port": int(os.getenv("AHREAS_SFTP_PORT", "22")),
        "sftp_user": os.getenv("AHREAS_SFTP_USER"),
        "sftp_password": os.getenv("AHREAS_SFTP_PASSWORD"),
        "remote_bak": os.getenv("AHREAS_REMOTE_BAK"),
        "local_bak": os.getenv("AHREAS_LOCAL_BAK"),

        "sql_server": os.getenv("SQL_SERVER_HOST"),
        "sql_database": os.getenv("SQL_SERVER_DATABASE", "master"),
        "sql_driver": os.getenv("SQL_SERVER_DRIVER", "ODBC Driver 17 for SQL Server"),
        "sql_user": os.getenv("SQL_SERVER_USER"),
        "sql_password": os.getenv("SQL_SERVER_PASSWORD"),
        "ahreas_database": os.getenv("AHREAS_DATABASE", "SIGADM"),

        "webmail_url": os.getenv("WEBMAIL_URL"),
        "webmail_user": os.getenv("WEBMAIL_USER"),
        "webmail_password": os.getenv("WEBMAIL_PASSWORD"),
        "destinatarios_erro": os.getenv("WEBMAIL_DESTINATARIOS_AHREAS"),
    }

    obrigatorias = [
        "sftp_host",
        "sftp_user",
        "sftp_password",
        "remote_bak",
        "local_bak",
        "sql_server",
        "sql_driver",
        "ahreas_database",
        "webmail_url",
        "webmail_user",
        "webmail_password",
        "destinatarios_erro",
    ]

    faltantes = [chave for chave in obrigatorias if not config.get(chave)]

    if faltantes:
        raise ValueError(
            "Variaveis obrigatorias nao preenchidas no .env: "
            + ", ".join(faltantes)
        )

    return config


# =====================================================================================
# SFTP
# =====================================================================================

def baixar_bak_sftp(config: dict) -> Path:
    local_bak = Path(config["local_bak"])
    temp_bak = local_bak.with_suffix(local_bak.suffix + ".download")

    local_bak.parent.mkdir(parents=True, exist_ok=True)

    if temp_bak.exists():
        log(f"Removendo download temporario anterior: {temp_bak}")
        temp_bak.unlink()

    log("Conectando ao SFTP.")
    transport = paramiko.Transport((config["sftp_host"], config["sftp_port"]))
    transport.connect(
        username=config["sftp_user"],
        password=config["sftp_password"]
    )

    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        remote_size = sftp.stat(config["remote_bak"]).st_size
        log(f"Arquivo remoto localizado: {config['remote_bak']}")
        log(f"Tamanho remoto: {remote_size:,} bytes")

        log(f"Iniciando download para arquivo temporario: {temp_bak}")
        def progresso_download(bytes_baixados, bytes_total):
            if bytes_total > 0:
                percentual = (bytes_baixados / bytes_total) * 100
                baixado_gb = bytes_baixados / (1024 ** 3)
                total_gb = bytes_total / (1024 ** 3)

                print(
                    f"\rDownload: {percentual:.2f}% "
                    f"({baixado_gb:.2f} GB de {total_gb:.2f} GB)",
                    end="",
                    flush=True
                )

        sftp.get(
            config["remote_bak"],
            str(temp_bak),
            callback=progresso_download
        )

        print()

        local_size = temp_bak.stat().st_size
        log(f"Tamanho local baixado: {local_size:,} bytes")

        if local_size != remote_size:
            raise RuntimeError(
                f"Download incompleto. Remoto={remote_size:,} bytes | "
                f"Local={local_size:,} bytes"
            )

        log("Download validado com sucesso pelo tamanho do arquivo.")

        if local_bak.exists():
            log(f"Removendo BAK local anterior: {local_bak}")
            local_bak.unlink()

        log(f"Renomeando temporario para arquivo oficial: {local_bak}")
        temp_bak.rename(local_bak)

        log("Arquivo BAK atualizado com sucesso.")
        return local_bak

    finally:
        try:
            sftp.close()
            transport.close()
            log("Conexao SFTP encerrada.")
        except Exception:
            pass


# =====================================================================================
# SQL SERVER
# =====================================================================================

def conectar_sql(config: dict):
    if config["sql_user"] and config["sql_password"]:
        conn_str = (
            f"DRIVER={{{config['sql_driver']}}};"
            f"SERVER={config['sql_server']};"
            f"DATABASE=master;"
            f"UID={config['sql_user']};"
            f"PWD={config['sql_password']};"
            "TrustServerCertificate=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{config['sql_driver']}}};"
            f"SERVER={config['sql_server']};"
            "DATABASE=master;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    conn = pyodbc.connect(conn_str, autocommit=True)
    conn.timeout = 0
    return conn


def obter_filelistonly(cursor, bak_path: Path) -> list[dict]:
    log("Lendo estrutura interna do BAK com RESTORE FILELISTONLY.")

    rows = cursor.execute(
        f"RESTORE FILELISTONLY FROM DISK = N'{str(bak_path)}'"
    ).fetchall()

    colunas = [column[0] for column in cursor.description]
    resultado = []

    for row in rows:
        item = dict(zip(colunas, row))
        resultado.append(item)

    if not resultado:
        raise RuntimeError("RESTORE FILELISTONLY nao retornou arquivos.")

    for item in resultado:
        log(
            f"Arquivo no BAK | LogicalName={item.get('LogicalName')} | "
            f"Type={item.get('Type')} | PhysicalName={item.get('PhysicalName')}"
        )

    return resultado


def obter_caminhos_atuais_banco(cursor, database: str) -> dict:
    log(f"Obtendo caminhos atuais do banco existente: {database}")

    query = """
    SELECT type_desc, physical_name
    FROM sys.master_files
    WHERE database_id = DB_ID(?)
    """

    rows = cursor.execute(query, database).fetchall()

    if not rows:
        raise RuntimeError(
            f"Nao foi possivel localizar arquivos atuais do banco {database}."
        )

    caminhos = {}

    for type_desc, physical_name in rows:
        caminhos[type_desc] = physical_name
        log(f"Arquivo atual | {type_desc}: {physical_name}")

    if "ROWS" not in caminhos:
        raise RuntimeError("Arquivo de dados ROWS nao localizado no banco atual.")

    if "LOG" not in caminhos:
        raise RuntimeError("Arquivo de log LOG nao localizado no banco atual.")

    return caminhos


def restaurar_banco(config: dict, bak_path: Path) -> None:
    database = config["ahreas_database"]

    log(f"Iniciando restauracao do banco {database} por cima do banco existente.")

    conn = conectar_sql(config)
    cursor = conn.cursor()

    try:
        filelist = obter_filelistonly(cursor, bak_path)
        caminhos_atuais = obter_caminhos_atuais_banco(cursor, database)

        logical_data = None
        logical_log = None

        for item in filelist:
            if item.get("Type") == "D" and logical_data is None:
                logical_data = item.get("LogicalName")
            elif item.get("Type") == "L" and logical_log is None:
                logical_log = item.get("LogicalName")

        if not logical_data:
            raise RuntimeError("LogicalName do arquivo de dados nao encontrado no BAK.")

        if not logical_log:
            raise RuntimeError("LogicalName do arquivo de log nao encontrado no BAK.")

        sql_restore = f"""
        ALTER DATABASE [{database}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;

        RESTORE DATABASE [{database}]
        FROM DISK = N'{str(bak_path)}'
        WITH REPLACE,
             RECOVERY,
             STATS = 5,
             MOVE N'{logical_data}' TO N'{caminhos_atuais["ROWS"]}',
             MOVE N'{logical_log}' TO N'{caminhos_atuais["LOG"]}';

        ALTER DATABASE [{database}] SET MULTI_USER;
        """

        log("Executando RESTORE DATABASE.")
        cursor.execute(sql_restore)

        while cursor.nextset():
            pass

        log("Comando RESTORE finalizado.")

        validar_restore(cursor, database)

    except Exception:
        try:
            log("Tentando retornar banco para MULTI_USER apos erro.")
            cursor.execute(f"ALTER DATABASE [{database}] SET MULTI_USER;")
        except Exception:
            pass
        raise

    finally:
        try:
            cursor.close()
            conn.close()
            log("Conexao SQL encerrada.")
        except Exception:
            pass


def validar_restore(cursor, database: str) -> None:
    log("Validando status do banco restaurado.")

    row = cursor.execute(
        """
        SELECT 
            name,
            state_desc,
            recovery_model_desc,
            user_access_desc
        FROM sys.databases
        WHERE name = ?
        """,
        database
    ).fetchone()

    if not row:
        raise RuntimeError(f"Banco {database} nao encontrado apos restore.")

    name, state_desc, recovery_model_desc, user_access_desc = row

    log(
        f"Status banco | name={name} | state={state_desc} | "
        f"recovery={recovery_model_desc} | user_access={user_access_desc}"
    )

    if state_desc != "ONLINE":
        raise RuntimeError(f"Banco {database} nao esta ONLINE. Estado: {state_desc}")

    if user_access_desc != "MULTI_USER":
        raise RuntimeError(
            f"Banco {database} nao voltou para MULTI_USER. Estado: {user_access_desc}"
        )

    teste = cursor.execute(f"SELECT DB_ID(N'{database}')").fetchone()[0]

    if not teste:
        raise RuntimeError(f"DB_ID do banco {database} nao foi localizado.")

    log("Restore validado com sucesso. Banco ONLINE e MULTI_USER.")


# =====================================================================================
# WEBMAIL - ENVIO DE ERRO
# =====================================================================================

def abrir_navegador():
    options = Options()
    options.add_argument("--disable-notifications")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    driver.maximize_window()
    return driver


def clicar_com_js(driver, elemento) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
    time.sleep(0.5)

    try:
        elemento.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elemento)


def clicar_botao_escrever(driver, wait) -> None:
    seletores = [
        (By.CSS_SELECTOR, "a.compose"),
        (By.CSS_SELECTOR, "a[title='Escrever nova mensagem']"),
        (By.CSS_SELECTOR, "a[href*='_action=compose']"),
        (By.CSS_SELECTOR, "a[onclick*='compose']"),
        (By.XPATH, "//a[contains(@class, 'compose')]"),
        (By.XPATH, "//a[.//span[contains(normalize-space(), 'Escrever')]]"),
        (By.XPATH, "//span[contains(normalize-space(), 'Escrever')]/ancestor::a[1]"),
    ]

    ultimo_erro = None

    for by, seletor in seletores:
        try:
            elemento = wait.until(EC.presence_of_element_located((by, seletor)))
            clicar_com_js(driver, elemento)
            time.sleep(4)
            return
        except Exception as exc:
            ultimo_erro = exc

    raise RuntimeError(
        f"Nao foi possivel localizar/clicar no botao Escrever. "
        f"Ultimo erro: {repr(ultimo_erro)}"
    )


def preencher_destinatarios(driver, wait, destinatarios: str) -> None:
    seletores = [
        "input[role='combobox']",
        "input[type='text'][autocomplete='off']",
        "textarea[name='_to']",
        "input[name='_to']",
        "input#_to",
    ]

    campo_to = None

    for seletor in seletores:
        try:
            campo_to = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
            )
            break
        except Exception:
            continue

    if campo_to is None:
        raise TimeoutException("Campo de destinatario nao encontrado.")

    driver.execute_script(
        """
        const campo = arguments[0];
        campo.focus();
        campo.value = arguments[1];
        campo.dispatchEvent(new Event('input', { bubbles: true }));
        campo.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        campo_to,
        destinatarios
    )

    time.sleep(1)


def preencher_assunto(driver, wait, assunto: str) -> None:
    campo_assunto = wait.until(
        EC.element_to_be_clickable((By.ID, "compose-subject"))
    )
    campo_assunto.clear()
    campo_assunto.send_keys(assunto)


def preencher_corpo(driver, wait, corpo: str) -> None:
    iframe = wait.until(
        EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "iframe[id*='composebody'], iframe.tox-edit-area__iframe, iframe"
        ))
    )

    driver.switch_to.frame(iframe)

    body = wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    corpo_html = (
        corpo.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    driver.execute_script(
        """
        const body = arguments[0];
        const html = arguments[1];

        const bloco = document.createElement('div');
        bloco.innerHTML = html + '<br><br>';

        body.insertBefore(bloco, body.firstChild);
        """,
        body,
        corpo_html,
    )

    driver.switch_to.default_content()


def enviar_email(driver, wait, timeout: int = 300) -> None:
    seletores = [
        (By.ID, "rcmbtn119"),
        (By.CSS_SELECTOR, "button.send"),
        (By.CSS_SELECTOR, "button.btn-primary.send"),
        (By.XPATH, "//button[contains(normalize-space(), 'Enviar')]"),
    ]

    botao = None

    for by, seletor in seletores:
        try:
            botao = wait.until(EC.element_to_be_clickable((by, seletor)))
            break
        except Exception:
            continue

    if botao is None:
        raise RuntimeError("Botao Enviar nao encontrado.")

    clicar_com_js(driver, botao)

    inicio = time.time()
    enviando_detectado = False

    while time.time() - inicio < timeout:
        try:
            texto = driver.find_element(By.TAG_NAME, "body").text

            if "Enviando mensagem" in texto:
                enviando_detectado = True
                time.sleep(3)
                continue

            if enviando_detectado and "Enviando mensagem" not in texto:
                return

            if (
                "Mensagem enviada" in texto
                or "mensagem enviada" in texto
                or "Message sent" in texto
            ):
                return

        except Exception:
            pass

        time.sleep(3)

    raise RuntimeError("Timeout aguardando confirmacao de envio do email.")


def enviar_email_erro(config: dict, erro: Exception, log_path: Path) -> None:
    driver = None

    try:
        assunto = "ERRO - Atualizacao Banco AHREAS"

        corpo = (
            "Ola!\n\n"
            "Ocorreu erro durante a rotina de atualizacao do banco AHREAS.\n\n"
            f"Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"Erro: {repr(erro)}\n"
            f"Log: {log_path}\n\n"
            "A rotina precisa ser verificada."
        )

        log("Abrindo navegador para envio de email de erro.")
        driver = abrir_navegador()
        wait = WebDriverWait(driver, 40)

        driver.get(config["webmail_url"])

        wait.until(
            EC.presence_of_element_located((By.ID, "rcmloginuser"))
        ).send_keys(config["webmail_user"])

        wait.until(
            EC.presence_of_element_located((By.ID, "rcmloginpwd"))
        ).send_keys(config["webmail_password"])

        wait.until(
            EC.element_to_be_clickable((By.ID, "rcmloginsubmit"))
        ).click()

        clicar_botao_escrever(driver, wait)
        preencher_destinatarios(driver, wait, config["destinatarios_erro"])
        preencher_assunto(driver, wait, assunto)
        preencher_corpo(driver, wait, corpo)
        enviar_email(driver, wait)

        log("Email de erro enviado com sucesso.")

    except Exception as erro_email:
        log(f"Falha ao enviar email de erro: {repr(erro_email)}")

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


# =====================================================================================
# MAIN
# =====================================================================================

def main() -> None:
    log_path = configurar_log()

    try:
        log("============================================================")
        log("INICIO - Atualizacao Banco AHREAS")
        log("============================================================")

        config = carregar_env()

        bak_path = baixar_bak_sftp(config)
        restaurar_banco(config, bak_path)

        log("============================================================")
        log("FIM - Atualizacao Banco AHREAS concluida com sucesso")
        log("============================================================")

    except Exception as erro:
        logging.exception("ERRO - Atualizacao Banco AHREAS falhou.")

        try:
            config = carregar_env()
            enviar_email_erro(config, erro, log_path)
        except Exception as erro_email_geral:
            log(f"Nao foi possivel enviar email de erro: {repr(erro_email_geral)}")

        raise


if __name__ == "__main__":
    main()