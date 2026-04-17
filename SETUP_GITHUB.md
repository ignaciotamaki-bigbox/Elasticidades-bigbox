# Setup — Día 1 (todo desde GitHub, sin terminal local)

**USAR ESTA GUÍA** (reemplaza a `SETUP.md`, que asume correr local).

Al terminar deberías poder disparar el workflow "Test Drive Download" en GitHub Actions y ver las primeras filas del Excel AR en los logs.

---

## Paso A — Crear el repo en GitHub

1. Entrar a https://github.com/new
2. Nombre sugerido: `elasticidades-bigbox`
3. Visibilidad: **Privado**
4. **NO** tildar "Add README", "Add .gitignore" ni "Add license"
5. **Create repository**

---

## Paso B — Subir los archivos al repo

Vas a subir 4 archivos + 1 workflow usando la UI web de GitHub. No necesitás git local ni Python local.

### B.1 — Archivos en la raíz

1. En el repo vacío, click en **uploading an existing file** (aparece en el texto de bienvenida), o **Add file → Upload files**
2. Arrastrar estos archivos desde la carpeta `repo/` que te dejé:
   - `test_download.py`
   - `requirements.txt`
   - `.gitignore`
   - `SETUP_GITHUB.md` (opcional, como referencia)
3. Scroll abajo → **Commit changes**

### B.2 — El workflow (archivo en subcarpeta)

1. **Add file → Create new file**
2. En el campo del nombre, escribí exactamente: `.github/workflows/test-drive.yml`
   (los `/` crean las carpetas automáticamente)
3. Pegar el contenido completo del archivo local `.github/workflows/test-drive.yml`
4. **Commit changes**

> Alternativa: algunos navegadores permiten arrastrar carpetas completas en "Upload files". Si el tuyo lo hace, arrastrá la carpeta `.github` directamente junto con los demás archivos.

---

## Paso C — Google Cloud + Service Account

~20 min, es la parte más larga pero se hace una sola vez.

### C.1 — Crear proyecto en Google Cloud

1. https://console.cloud.google.com
2. Selector de proyectos arriba → **New Project**
3. Nombre: `elasticidades-bigbox`
4. **Create**, esperar ~30 seg
5. Verificar que el proyecto nuevo esté seleccionado arriba

### C.2 — Habilitar Google Drive API

1. Buscador de arriba: "Google Drive API"
2. Click en el resultado → **Enable**

### C.3 — Crear Service Account

1. Buscador de arriba: "Service Accounts"
2. **+ Create Service Account**
3. Nombre: `elasticidades-reader`
4. **Create and Continue**
5. En "Grant access to project": **Skip**
6. **Done**

### C.4 — Generar la key (JSON)

1. Click en el Service Account recién creado
2. Tab **Keys**
3. **Add Key → Create new key → JSON → Create**
4. Se descarga un JSON. Guardalo en un lugar seguro de tu computadora (lo vas a copiar al secret en el paso E).

> Este archivo es sensible. Nunca subirlo al repo directamente.

### C.5 — Copiar el email del Service Account

Se ve así: `elasticidades-reader@elasticidades-bigbox.iam.gserviceaccount.com`

---

## Paso D — Compartir los Excels con el Service Account

En Google Drive, por cada Excel (AR, CL, UY):

1. Click derecho → **Share**
2. Pegar el email del Service Account
3. Permiso: **Viewer**
4. **Share** (desmarcar "Notify people")

### Copiar el File ID del Excel AR

Abrí el Excel AR en Drive. La URL se ve así:
```
https://drive.google.com/file/d/1a2b3c4d5e6f7g8h9i/view?usp=sharing
                                └──── ESTO ES EL ID ────┘
```

Copialo, lo vamos a usar en el próximo paso.

(Para el test de hoy solo necesitás el ID del AR. Después agregamos CL y UY.)

---

## Paso E — Agregar secrets en GitHub

1. En el repo de GitHub: **Settings** (arriba a la derecha del repo)
2. Menú izquierdo: **Secrets and variables → Actions**
3. Botón **New repository secret**

Crear estos 2 secrets:

**Secret 1**
- Name: `GOOGLE_CREDENTIALS`
- Value: pegar el contenido COMPLETO del JSON que descargaste en C.4
  (abrilo con Notepad o VS Code, Ctrl+A, Ctrl+C, Ctrl+V en el campo de Value)

**Secret 2**
- Name: `FILE_ID_AR`
- Value: el file ID que copiaste en el paso D

---

## Paso F — Correr el workflow

1. En el repo, pestaña **Actions** (arriba)
2. La primera vez puede aparecer un banner pidiendo habilitar workflows → **I understand my workflows, go ahead and enable them**
3. En la barra izquierda: **Test Drive Download**
4. Botón **Run workflow** (derecha) → **Run workflow** (botón verde)
5. Esperar 30-60 seg, la página se refresca sola
6. Click en el run que aparece → click en el job `test`
7. Expandir el step **Run test script** para ver la salida

### Qué esperar como salida exitosa

```
Autenticando con credentials.json...
Bajando archivo 1a2b3c...
  descargando... 100%
OK: 227,710 bytes descargados

Hojas del Excel:
  - <los nombres de las hojas>

Preview de '<primera hoja>':
  Columnas: [...]
  Filas: NN

Primeras 5 filas:
  <tabla>

[OK] Todo funciona. Listos para el Dia 2.
```

### Si algo falla

- **"el secret GOOGLE_CREDENTIALS está vacío"** → el secret no quedó guardado, o se llama distinto. Revisá Settings → Secrets.
- **"Falta FILE_ID_AR"** → mismo lugar, falta el otro secret.
- **"403 Forbidden" o "File not found"** → no compartiste el Excel con el Service Account, o el File ID está mal copiado.
- **No aparece "Test Drive Download" en Actions** → el archivo `.github/workflows/test-drive.yml` no está en el repo, o el path está mal. Tiene que empezar con el punto (`.github`).

Copiame el error del log y lo resolvemos juntos.
