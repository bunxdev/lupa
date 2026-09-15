---
name: lupa-local-leads
description: Reúne contactos públicos de negocios por giro y municipio usando Google Maps en la sesión visible de Lupa mediante Browser Use/CDP. Úsala para buscar leads locales, repetir una prospección con otro giro, exportar contactos o reanudar una búsqueda guardada. Genera CSV, JSON y HTML con fuentes; puede añadir correos y WhatsApp publicados en sitios oficiales.
---

# Contactos locales con Lupa

Trabaja desde la raíz del repositorio Lupa que contiene `integrations/browser-use/run.py`. Si no estás allí, localiza el checkout existente; no presupongas una ruta absoluta. Requiere Python 3, Docker y Lupa iniciada con `/cdp`. El ejecutor construye el cliente si hace falta y obtiene el token sin mostrarlo. Usa la misma pestaña de `/live`, visible en Selkies; no inicies otro navegador.

## Recopilar

Deduce giro, municipio y cantidad del contexto. Si sólo cambia el giro, conserva la ubicación y cantidad previas; sin cantidad previa usa 15 e indica la suposición. Usa consultas separadas para varios giros: se alternan candidatos entre consultas. Elige una carpeta nueva por ejecución.

```sh
python3 integrations/browser-use/run.py leads \
  --query 'peluquerías en Zapopan' --query 'barberías en Zapopan' \
  --municipality Zapopan --limit 15 \
  --category peluquer --category barber --category belleza \
  --category hair --category beauty \
  --output /output/leads-peluquerias-barberias-zapopan-AAAAMMDD
```

Adapta `--category` al giro y a los idiomas que aparezcan en Maps. Es un filtro por fragmento de categoría; omitirlo requiere revisar manualmente la relevancia de los resultados. La dirección debe confirmar el municipio; una consulta geográfica puede incluir localidades vecinas. Se excluyen fichas sin teléfono público, cierres permanentes y duplicados por teléfono, Maps o nombre/dirección. No se extraen reseñas ni identidades de sus autores.

`/output/` se guarda en `downloads/` del repositorio. Cada ficha produce un checkpoint en `state.json`; `leads.csv`, `leads.json` y `leads.html` contienen los contactos aceptados. Para reanudar, repite el comando con `--resume`. Si faltan contactos, revisa `rejected` y `errors` antes de cambiar consultas o filtros en una carpeta nueva. Un error conserva resultados parciales; no declares alcanzada la cantidad si no lo está. Ante CAPTCHA o bloqueo, conserva el avance y comunica la limitación.

## Enriquecer y revisar

Visita los sitios oficiales enlazados por las fichas para localizar canales adicionales. Mantén la fuente exacta de cada dato. No inventes correos ni conviertas un teléfono en WhatsApp por suposición. Si dos fuentes discrepan, conserva el dato de Maps y explica la alternativa en notas con su fuente. No llames ni envíes mensajes como parte de la recopilación.

Para incorporar hechos verificados, crea un JSON como éste, reemplazando valores por datos reales observados:

```json
[
  {
    "maps": "https://www.google.com/maps?cid=IDENTIFICADOR_REAL",
    "email": {"value": "correo@dominio-del-negocio.mx", "source": "https://dominio-del-negocio.mx/contacto"},
    "whatsapp": {"value": "https://wa.me/NUMERO_PUBLICADO", "source": "https://dominio-del-negocio.mx/contacto"},
    "notes": "Observaciones verificadas pertinentes."
  }
]
```

Omite los campos no localizados. El identificador Maps debe coincidir con `leads.json`.

```sh
python3 integrations/browser-use/export_leads.py downloads/CARPETA --enrichment downloads/CARPETA/enrichment.json
```

Revisa cantidad, municipio, relevancia y teléfonos únicos en `leads.json`. Las fuentes acreditan publicación, no vigencia por llamada ni interés comercial. Entrega enlaces al CSV y HTML, número real de contactos y límites concretos. Presenta los negocios como prospectos sin contactar ni calificar. Para mostrar el informe en Lupa, usa el comando `report` indicado al final; Browser Use puede rechazar URLs `file:` al conectar Actor.

## Mantenimiento

Scripts: `integrations/browser-use/leads.py` (navegación y checkpoints), `lead_data.py` (normalización, filtros y exportación), `export_leads.py` (enriquecimiento sin navegador). Documentación de comandos: `integrations/browser-use/README.md`.

Después de modificar reglas de extracción o exportación, ejecuta:

```sh
python3 -m unittest discover -s integrations/browser-use -p 'test_lead_data.py'
```

Los selectores de Maps pueden cambiar: inspecciona el DOM actual con `run.py inspect` y actualiza sólo lo necesario. No desactives los filtros para aparentar una ejecución completa.

Puedes ampliar una ejecución con `--resume --limit 100` y añadir consultas: conserva municipio y filtros de categoría. Se mantienen los contactos guardados y se descubren candidatos nuevos. El límite no puede ser inferior a la cantidad ya guardada.

Abre el informe local en la sesión visible sin conectar Actor (que puede rechazar `file:`):

```sh
python3 integrations/browser-use/run.py report /output/CARPETA/leads.html
```

Revisa también el nombre y la actividad: Maps puede clasificar una estética canina como «Peluquería». Para retirar una ficha revisada, usa `export_leads.py downloads/CARPETA --exclude-maps 'URL exacta' --reason 'Motivo verificado' --review-source 'URL fuente'`; conserva su evidencia y reanuda para cubrir el faltante. Ejecuta el exportador sólo cuando el recolector haya terminado para evitar escrituras simultáneas.
