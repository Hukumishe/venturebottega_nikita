# WebTV Data Source

## Source

WebTV data comes from the **Camera dei Deputati** (Italian Chamber of Deputies) website.

## URL Pattern

```
https://documenti.camera.it/apps/commonServices/getDocumento.ashx?sezione=assemblea&tipoDoc=formato_xml&tipologia=stenografico&idNumero={session_number}&idLegislatura={legislature}
```

### Parameters:
- `sezione=assemblea` - Assembly section
- `tipoDoc=formato_xml` - XML format document
- `tipologia=stenografico` - Stenographic transcript
- `idNumero={session_number}` - Session number (e.g., 347, 348, 349...)
- `idLegislatura={legislature}` - Legislature number (e.g., 19 for current)

### Example URLs:
- Session 347: `https://documenti.camera.it/apps/commonServices/getDocumento.ashx?sezione=assemblea&tipoDoc=formato_xml&tipologia=stenografico&idNumero=0347&idLegislatura=19`
- Session 448: `https://documenti.camera.it/apps/commonServices/getDocumento.ashx?sezione=assemblea&tipoDoc=formato_xml&tipologia=stenografico&idNumero=0448&idLegislatura=19`

## Data Format

The API returns **XML** that needs to be parsed:
- Root element: `<seduta>` (session)
- Contains: `<dibattito>` (debate/topic) elements
- Each debate has: `<titolo>` (title) and `<intervento>` (intervention/speech) elements
- Each intervention has: `<nominativo>` (speaker name) and `<testoXHTML>` (text)

## Current Process

1. **Fetch XML** from Camera website
2. **Parse XML** using BeautifulSoup
3. **Extract**:
   - Session info (legislature, session number, date)
   - Topics (dibattiti)
   - Interventions (speeches) with speaker names and text
4. **Convert to JSON** format
5. **Process** into database (Session, Topic, SpeechSegment models)

## Data Structure

After parsing, the JSON structure is:
```json
{
  "contents": {
    "Topic Title 1": [
      {
        "speaker": "COGNOME Nome",
        "text": "Speech text..."
      },
      ...
    ],
    "Topic Title 2": [...]
  }
}
```

## Finding Session Numbers

Session numbers are sequential but not always consecutive:
- Start from session 1 of the legislature
- Some numbers may be skipped
- Need to check which sessions exist

## Limitations

- **No official API**: This is scraping from a public document service
- **Rate limiting**: Should add delays between requests
- **Session discovery**: Need to know which session numbers exist
- **XML parsing**: Requires BeautifulSoup/lxml
- **Date extraction**: Session dates are in XML but need proper parsing

## Future Enhancements

1. **Session discovery**: Find available session numbers automatically
2. **Date extraction**: Parse actual session dates from XML
3. **Incremental updates**: Only fetch new sessions
4. **Error handling**: Better handling of missing/invalid sessions
5. **Senato support**: Add support for Senate sessions (different URL pattern)

