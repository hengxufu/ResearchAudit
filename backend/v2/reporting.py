"""Paginated PDF report with source identifiers; rendered from stored observations."""
from io import BytesIO
import json,hashlib,time,threading
PDF_LOCK=threading.RLock()
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont,TTFError
from pathlib import Path
import os
from .. import storage
from ..analysis import audit

def _pdf(id):
    snapshot=storage.get(id);out=BytesIO();styles=getSampleStyleSheet()
    font='STSong-Light'
    candidate=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'msyh.ttc'
    if candidate.is_file():
        try:
            pdfmetrics.registerFont(TTFont('ResearchAuditUnicode',str(candidate),subfontIndex=0));font='ResearchAuditUnicode'
        except TTFError:pass
    if font=='STSong-Light':pdfmetrics.registerFont(UnicodeCIDFont(font))
    for name in ('Normal','Heading1','Heading2'):
        styles[name].fontName=font;styles[name].wordWrap='CJK'
    story=[Paragraph('ResearchAudit - Experiment Evidence Report',styles['Heading1']),Paragraph('Snapshot '+str(id),styles['Normal']),Paragraph(escape(snapshot['root']),styles['Normal']),Spacer(1,12)]
    for run in snapshot['runs']:
        story.append(Paragraph(escape(run['name']),styles['Heading2']))
        data=[[Paragraph(escape(text),styles['Normal']) for text in ['Metric','Final value','Method']]]+[[Paragraph(escape(str(text)),styles['Normal']) for text in (m,str(v),'Last observation')] for m,v in run['metrics'].items()]
        table=Table(data,colWidths=[180,100,180],repeatRows=1,hAlign='LEFT');table.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),font),('FONTSIZE',(0,0),(-1,-1),9),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbeafe')),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)]));story.extend([table,Spacer(1,10)])
        for source in run['sources']:
            story.append(Paragraph(escape(source['path'])+'<br/>SHA256: '+escape(source['sha256']),styles['Normal']))
    analyses=[]
    with storage.connect() as c:
        if c.execute("SELECT name FROM sqlite_master WHERE name='analyses' AND type='table'").fetchone():
            for record in c.execute('SELECT id,payload FROM analyses'):
                value=json.loads(record[1])
                if value.get('inputs',{}).get('snapshot_id')==id or any(isinstance(s,dict) and s.get('reference',{}).get('snapshot_id')==id for s in value.get('sources',[])):analyses.append({'id':record[0],**value})
    if analyses:
        story.append(Paragraph('Persisted analyses - methods and results',styles['Heading2']))
        for value in analyses:
            story.append(Paragraph(escape(value['method']+' | '+value['id']),styles['Normal']))
            story.append(Paragraph(escape(json.dumps(value['result'],ensure_ascii=False)),styles['Normal']))
    story.append(Paragraph('Audit - Evidence scope, not scientific correctness' ,styles['Heading2']))
    for f in audit(snapshot):story.append(Paragraph(escape(f['status']+' | '+f['rule']+' | '+str(f.get('reason',f.get('message','')))),styles['Normal']))
    def footer(canvas,doc):canvas.setFont('Helvetica',9);canvas.drawString(40,25,'ResearchAudit | Snapshot '+str(id)+' | Page '+str(doc.page))
    SimpleDocTemplate(out,pagesize=(595,842),leftMargin=40,rightMargin=40,topMargin=40,bottomMargin=45,invariant=1).build(story,onFirstPage=footer,onLaterPages=footer)
    data=out.getvalue();rid=hashlib.sha256(data).hexdigest()
    with storage.connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS report_records(id TEXT PRIMARY KEY,snapshot_id INTEGER,created REAL,spec TEXT)')
        c.execute('INSERT OR IGNORE INTO report_records VALUES (?,?,?,?)',(rid,id,time.time(),json.dumps({'method':'pdf-report-v2','analysis_ids':[a['id'] for a in analyses],'sha256':rid})))
    return data


def pdf(id):
    with PDF_LOCK:return _pdf(id)
