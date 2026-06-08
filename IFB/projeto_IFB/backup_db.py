import os
import shutil
from datetime import datetime

# Caminho do banco de dados SQLite (relativo à raiz)
DB_PATH = 'db.sqlite3'
BACKUP_DIR = 'backups'

# Cria a pasta de backups se não existir
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Gera nome do arquivo com timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_name = f'{BACKUP_DIR}/db_backup_{timestamp}.sqlite3'

# Copia o arquivo
shutil.copy(DB_PATH, backup_name)
print(f'Backup criado: {backup_name}')