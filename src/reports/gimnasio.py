from pathlib import Path
from html import escape
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape

def tablas(ingresos,membresias):
    return [
        ('Ingresos',['Fecha y hora','Socio','DNI','Plan'],[
            [i['instante'].strftime('%d/%m/%Y %H:%M:%S'),f"{i['apellido']}, {i['nombre']}",i['dni'],i['plan']] for i in ingresos]),
        ('Membresías actuales',['Socio','DNI','Plan','Inicio','Vence','Usados','Restantes','Estado'],[
            [f"{m['apellido']}, {m['nombre']}",m['dni'],m['plan'] or 'Sin plan',str(m['inicio'] or '—'),str(m['vence'] or '—'),m['usados'],
             m['restantes'] if m['cupo'] else ('Sin cupo' if m['plan'] else '—'),m['estado']] for m in membresias])]

def exportar(ruta,ingresos,membresias,desde,hasta):
    datos=tablas(ingresos,membresias)
    periodo=f'Ingresos: {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}. Membresías: estado actual al exportar.'
    if Path(ruta).suffix.lower()=='.xlsx':
        libro=Workbook(); libro.remove(libro.active)
        for titulo,cabeceras,filas in datos:
            hoja=libro.create_sheet(titulo); hoja.append(['PULSO GYM']); hoja.append([periodo]); hoja.append(cabeceras)
            for fila in filas:
                hoja.append(fila)
                for celda in hoja[hoja.max_row]:
                    if isinstance(celda.value,str): celda.data_type='s'
            for celda in hoja[3]:
                celda.font=Font(color='B8F34A',bold=True); celda.fill=PatternFill('solid',fgColor='142438')
            hoja.freeze_panes='A4'; hoja.auto_filter.ref=f'A3:{hoja.cell(hoja.max_row,len(cabeceras)).coordinate}'
            for columna in hoja.columns:
                hoja.column_dimensions[columna[0].column_letter].width=min(38,max(14,max(len(str(c.value or '')) for c in columna[2:])+2))
        libro.save(ruta)
    else:
        estilos=getSampleStyleSheet(); estilo=estilos['BodyText']; estilo.fontSize=8; estilo.leading=11
        historia=[Paragraph('PULSO GYM | Control de acceso',estilos['Title']),Paragraph(escape(periodo),estilo),Spacer(1,14)]
        for numero,(titulo,cabeceras,filas) in enumerate(datos):
            if numero: historia.append(PageBreak())
            historia.append(Paragraph(titulo,estilos['Heading1']))
            celdas=[[Paragraph(escape(str(x)),estilo) for x in cabeceras]]
            celdas.extend([[Paragraph(escape(str(x)),estilo) for x in f] for f in filas])
            if not filas: celdas.append([Paragraph('Sin registros',estilo)]+['']*(len(cabeceras)-1))
            anchos=[140,140,100,390] if numero==0 else [135,75,125,75,75,55,75,155]
            factor=770/sum(anchos); anchos=[a*factor for a in anchos]
            t=Table(celdas,colWidths=anchos,repeatRows=1)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#b8f34a')),
                                  ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#edf2f5')]),
                                  ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),
                                  ('TOPPADDING',(0,0),(-1,-1),8)]))
            historia.append(t)
        def pie(canvas,doc):
            canvas.setFont('Helvetica',8); canvas.drawString(36,20,'PULSO GYM · Informe de recepción'); canvas.drawRightString(805,20,str(doc.page))
        SimpleDocTemplate(ruta,pagesize=landscape(A4),leftMargin=36,rightMargin=36,topMargin=32,bottomMargin=36).build(historia,onFirstPage=pie,onLaterPages=pie)
