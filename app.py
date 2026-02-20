from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import os
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fedeles-fogathajto-titkos-kulcs-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fogathajto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==================== ADATBÁZIS MODELLEK ====================

class Verseny(db.Model):
    __tablename__ = 'versenyek'
    id = db.Column(db.Integer, primary_key=True)
    nev = db.Column(db.String(100), nullable=False)
    datum = db.Column(db.String(20), nullable=False)
    aktiv = db.Column(db.Boolean, default=True)
    lezart = db.Column(db.Boolean, default=False)

class Versenyzo(db.Model):
    __tablename__ = 'versenyzok'
    id = db.Column(db.Integer, primary_key=True)
    verseny_id = db.Column(db.Integer, db.ForeignKey('versenyek.id'), nullable=False)
    startszam = db.Column(db.Integer, nullable=False)
    nev = db.Column(db.String(100), nullable=False)
    kategoria = db.Column(db.String(50), nullable=False)
    nemzetiseg = db.Column(db.String(50), nullable=False)
    
    # Státusz mezők
    f1_statusz = db.Column(db.String(20), default='')
    f2_statusz = db.Column(db.String(20), default='')
    ov_statusz = db.Column(db.String(20), default='')
    
    # 1. forduló
    f1_verohibak = db.Column(db.Text, default='{}')
    f1_egyeb_hiba = db.Column(db.Integer, default=0)
    f1_ido = db.Column(db.Float, default=0)
    f1_ossz_hiba = db.Column(db.Integer, default=0)
    
    # 2. forduló
    f2_verohibak = db.Column(db.Text, default='{}')
    f2_egyeb_hiba = db.Column(db.Integer, default=0)
    f2_ido = db.Column(db.Float, default=0)
    f2_ossz_hiba = db.Column(db.Integer, default=0)
    
    # Összevetés
    ov_verohibak = db.Column(db.Text, default='{}')
    ov_egyeb_hiba = db.Column(db.Integer, default=0)
    ov_ido = db.Column(db.Float, default=0)
    ov_ossz_hiba = db.Column(db.Integer, default=0)
    
    # Sorrend adatok
    f1_sorrend = db.Column(db.Integer)
    f2_sorrend = db.Column(db.Integer)
    ov_sorrend = db.Column(db.Integer)
    osszevetesre_jogosult = db.Column(db.Boolean, default=False)

# ==================== ADATBÁZIS LÉTREHOZÁS ====================

with app.app_context():
    db.create_all()
    print("✅ Adatbázis ellenőrizve!")

# ==================== FŐOLDAL ====================

@app.route('/')
def index():
    versenyek = Verseny.query.filter_by(lezart=False).order_by(Verseny.datum.desc()).all()
    aktualis_verseny_id = session.get('aktualis_verseny_id')
    aktualis_verseny = None
    if aktualis_verseny_id:
        aktualis_verseny = Verseny.query.get(aktualis_verseny_id)
    return render_template('index.html', versenyek=versenyek, aktualis_verseny=aktualis_verseny)

# ==================== VERSENY KEZELÉS ====================

@app.route('/verseny_inditas', methods=['GET', 'POST'])
def verseny_inditas():
    if request.method == 'POST':
        nev = request.form['nev']
        datum = request.form['datum']
        uj_verseny = Verseny(nev=nev, datum=datum, aktiv=True, lezart=False)
        db.session.add(uj_verseny)
        db.session.commit()
        session['aktualis_verseny_id'] = uj_verseny.id
        return redirect(url_for('versenyzo_felvitel', verseny_id=uj_verseny.id))
    return render_template('verseny_inditas.html')

@app.route('/verseny_valaszt/<int:verseny_id>')
def verseny_valaszt(verseny_id):
    verseny = Verseny.query.get_or_404(verseny_id)
    if not verseny.lezart:
        session['aktualis_verseny_id'] = verseny_id
    return redirect(url_for('verseny_fooldal', verseny_id=verseny_id))

@app.route('/verseny_fooldal/<int:verseny_id>')
def verseny_fooldal(verseny_id):
    verseny = Verseny.query.get_or_404(verseny_id)
    versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).all()
    
    kategoriak = {}
    for v in versenyzok:
        if v.kategoria not in kategoriak:
            kategoriak[v.kategoria] = []
        kategoriak[v.kategoria].append(v)
    
    return render_template('verseny_fooldal.html', verseny=verseny, kategoriak=kategoriak)

@app.route('/verseny_lezaras/<int:verseny_id>', methods=['POST'])
def verseny_lezaras(verseny_id):
    verseny = Verseny.query.get_or_404(verseny_id)
    verseny.lezart = True
    verseny.aktiv = False
    db.session.commit()
    session.pop('aktualis_verseny_id', None)
    return jsonify({'success': True, 'message': 'Verseny lezárva!'})

# ==================== VERSENYZŐK ====================

@app.route('/versenyzo_felvitel/<int:verseny_id>', methods=['GET', 'POST'])
def versenyzo_felvitel(verseny_id):
    if request.method == 'POST':
        startszam = request.form['startszam']
        nev = request.form['nev']
        kategoria = request.form['kategoria']
        nemzetiseg = request.form['nemzetiseg']
        
        letezo = Versenyzo.query.filter_by(verseny_id=verseny_id, startszam=startszam).first()
        if letezo:
            return jsonify({'error': 'Ez a startszám már létezik!'}), 400
        
        uj = Versenyzo(
            verseny_id=verseny_id,
            startszam=startszam,
            nev=nev,
            kategoria=kategoria,
            nemzetiseg=nemzetiseg
        )
        db.session.add(uj)
        db.session.commit()
        return jsonify({'success': True, 'message': f'{nev} rögzítve!'})
    
    versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).order_by(Versenyzo.kategoria, Versenyzo.startszam).all()
    return render_template('versenyzo_felvitel.html', verseny_id=verseny_id, versenyzok=versenyzok)

@app.route('/eredmeny_rögzites/<int:verseny_id>/<int:startszam>')
def eredmeny_rögzites(verseny_id, startszam):
    versenyzo = Versenyzo.query.filter_by(verseny_id=verseny_id, startszam=startszam).first_or_404()
    return render_template('eredmeny_rögzites.html', versenyzo=versenyzo)

# ==================== STARTLISTA KEZELÉS ====================

@app.route('/startlista/<int:verseny_id>')
def startlista(verseny_id):
    try:
        verseny = Verseny.query.get_or_404(verseny_id)
        versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).order_by(Versenyzo.kategoria, Versenyzo.f1_sorrend).all()
        
        kategoriak = {}
        for v in versenyzok:
            if v.kategoria not in kategoriak:
                kategoriak[v.kategoria] = []
            kategoriak[v.kategoria].append(v)
        
        for kat in kategoriak:
            kategoriak[kat] = sorted(kategoriak[kat], key=lambda x: x.f1_sorrend or x.startszam)
        
        return render_template('startlista.html', verseny=verseny, kategoriak=kategoriak)
    except Exception as e:
        return f"Hiba: {str(e)}", 500

@app.route('/api/startlista_mentes', methods=['POST'])
def api_startlista_mentes():
    try:
        data = request.json
        verseny_id = data['verseny_id']
        sorrend = data['sorrend']
        
        for kategoria, startszamok in sorrend.items():
            for index, startszam in enumerate(startszamok):
                versenyzo = Versenyzo.query.filter_by(verseny_id=verseny_id, startszam=startszam).first()
                if versenyzo:
                    versenyzo.f1_sorrend = index + 1
                    db.session.add(versenyzo)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== API EREDMÉNY MENTÉS ====================

@app.route('/api/eredmeny_mentes', methods=['POST'])
def api_eredmeny_mentes():
    data = request.json
    versenyzo_id = data['versenyzo_id']
    fordulo = data['fordulo']
    statusz = data.get('statusz', '')
    verohibak = data['verohibak']
    egyeb_hiba = data['egyeb_hiba']
    ido = data['ido']
    
    versenyzo = Versenyzo.query.get(versenyzo_id)
    
    verohiba_pont = 0
    for hiba in verohibak.values():
        verohiba_pont += hiba * 4
    
    ossz_hiba = verohiba_pont + egyeb_hiba
    
    if fordulo == 'f1':
        versenyzo.f1_statusz = statusz
        versenyzo.f1_verohibak = json.dumps(verohibak)
        versenyzo.f1_egyeb_hiba = egyeb_hiba
        versenyzo.f1_ido = ido
        versenyzo.f1_ossz_hiba = ossz_hiba
    elif fordulo == 'f2':
        versenyzo.f2_statusz = statusz
        versenyzo.f2_verohibak = json.dumps(verohibak)
        versenyzo.f2_egyeb_hiba = egyeb_hiba
        versenyzo.f2_ido = ido
        versenyzo.f2_ossz_hiba = ossz_hiba
    elif fordulo == 'ov':
        versenyzo.ov_statusz = statusz
        versenyzo.ov_verohibak = json.dumps(verohibak)
        versenyzo.ov_egyeb_hiba = egyeb_hiba
        versenyzo.ov_ido = ido
        versenyzo.ov_ossz_hiba = ossz_hiba
    
    db.session.commit()
    return jsonify({'success': True})

# ==================== 2. FORDULÓ SORREND ====================

@app.route('/api/f2_sorrend_modositas', methods=['POST'])
def api_f2_sorrend_modositas():
    try:
        data = request.json
        verseny_id = data['verseny_id']
        sorrend = data['sorrend']
        
        for index, startszam in enumerate(sorrend):
            versenyzo = Versenyzo.query.filter_by(verseny_id=verseny_id, startszam=startszam).first()
            if versenyzo:
                versenyzo.f2_sorrend = index + 1
                db.session.add(versenyzo)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== NÉZŐI FELÜLET ====================

@app.route('/nezok/<int:verseny_id>')
def nezok(verseny_id):
    try:
        verseny = Verseny.query.get_or_404(verseny_id)
        return render_template('nezok.html', verseny=verseny)
    except Exception as e:
        return str(e), 500

@app.route('/api/nezok_adatok/<int:verseny_id>')
def api_nezok_adatok(verseny_id):
    try:
        verseny = Verseny.query.get_or_404(verseny_id)
        versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).all()
        
        kategoriak = {}
        for v in versenyzok:
            if v.kategoria not in kategoriak:
                kategoriak[v.kategoria] = {
                    'f1_minden': [],
                    'f2_minden': [],
                    'ov': []
                }
            
            kategoriak[v.kategoria]['f1_minden'].append({
                'startszam': v.startszam,
                'nev': v.nev,
                'nemzetiseg': v.nemzetiseg,
                'hiba': v.f1_ossz_hiba,
                'ido': v.f1_ido,
                'ido_raw': v.f1_ido,
                'statusz': v.f1_statusz
            })
            
            kategoriak[v.kategoria]['f2_minden'].append({
                'startszam': v.startszam,
                'nev': v.nev,
                'nemzetiseg': v.nemzetiseg,
                'hiba': v.f2_ossz_hiba,
                'ido': v.f2_ido,
                'ido_raw': v.f2_ido,
                'statusz': v.f2_statusz
            })
            
            if v.osszevetesre_jogosult:
                kategoriak[v.kategoria]['ov'].append({
                    'startszam': v.startszam,
                    'nev': v.nev,
                    'nemzetiseg': v.nemzetiseg,
                    'hiba': v.ov_ossz_hiba,
                    'ido': v.ov_ido,
                    'ido_raw': v.ov_ido,
                    'statusz': v.ov_statusz
                })
        
        return jsonify({
            'verseny_neve': verseny.nev,
            'verseny_datum': verseny.datum,
            'kategoriak': kategoriak
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== PDF EXPORT ====================

@app.route('/export/startlista_pdf/<int:verseny_id>')
def export_startlista_pdf(verseny_id):
    try:
        verseny = Verseny.query.get_or_404(verseny_id)
        versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).order_by(Versenyzo.kategoria, Versenyzo.f1_sorrend).all()
        
        kategoriak = {}
        for v in versenyzok:
            if v.kategoria not in kategoriak:
                kategoriak[v.kategoria] = []
            kategoriak[v.kategoria].append(v)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            textColor=colors.purple,
            alignment=1,
            spaceAfter=12
        )
        story.append(Paragraph("Fedeles Fogathajtó Verseny", title_style))
        story.append(Paragraph(f"{verseny.nev} - {verseny.datum}", styles['Heading2']))
        story.append(Paragraph("STARTLISTA", styles['Heading3']))
        story.append(Spacer(1, 20))
        
        for kategoria, lista in kategoriak.items():
            story.append(Paragraph(kategoria, styles['Heading3']))
            story.append(Spacer(1, 10))
            
            adatok = [['Rajtszám', 'Versenyző', 'Nemzetiség', 'Rajtsorrend']]
            for v in lista:
                adatok.append([
                    str(v.startszam),
                    v.nev,
                    v.nemzetiseg,
                    str(v.f1_sorrend or v.startszam)
                ])
            
            table = Table(adatok, colWidths=[60, 200, 80, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.purple),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'startlista_{verseny.nev}_{verseny.datum}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return str(e), 500

@app.route('/export/eredmenyek_pdf/<int:verseny_id>')
def export_eredmenyek_pdf(verseny_id):
    try:
        verseny = Verseny.query.get_or_404(verseny_id)
        versenyzok = Versenyzo.query.filter_by(verseny_id=verseny_id).all()
        
        kategoriak = {}
        for v in versenyzok:
            if v.kategoria not in kategoriak:
                kategoriak[v.kategoria] = []
            kategoriak[v.kategoria].append(v)
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            textColor=colors.purple,
            alignment=1,
            spaceAfter=12
        )
        story.append(Paragraph("Fedeles Fogathajtó Verseny", title_style))
        story.append(Paragraph(f"{verseny.nev} - {verseny.datum}", styles['Heading2']))
        story.append(Paragraph("EREDMÉNYEK", styles['Heading3']))
        story.append(Spacer(1, 20))
        
        for kategoria, lista in kategoriak.items():
            story.append(Paragraph(kategoria, styles['Heading3']))
            story.append(Spacer(1, 10))
            
            # 1. Forduló
            story.append(Paragraph("1. Forduló", styles['Heading4']))
            adatok = [['Hely', 'Rajtszám', 'Versenyző', 'Nemzetiség', 'Hiba', 'Idő']]
            f1_lista = [v for v in lista if v.f1_ido > 0]
            f1_lista.sort(key=lambda x: (x.f1_ossz_hiba, x.f1_ido))
            
            for idx, v in enumerate(f1_lista, 1):
                ido_str = f"{v.f1_ido:.2f}" if v.f1_ido else '--:--'
                hiba_str = str(v.f1_ossz_hiba) if not v.f1_statusz else v.f1_statusz
                adatok.append([str(idx), str(v.startszam), v.nev, v.nemzetiseg, hiba_str, ido_str])
            
            if len(adatok) > 1:
                table = Table(adatok, colWidths=[40, 60, 140, 60, 60, 70])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(table)
                story.append(Spacer(1, 15))
            
            # 2. Forduló
            story.append(Paragraph("2. Forduló", styles['Heading4']))
            adatok = [['Hely', 'Rajtszám', 'Versenyző', 'Nemzetiség', 'Hiba', 'Idő']]
            f2_lista = [v for v in lista if v.f2_ido > 0]
            f2_lista.sort(key=lambda x: (x.f2_ossz_hiba, x.f2_ido))
            
            for idx, v in enumerate(f2_lista, 1):
                ido_str = f"{v.f2_ido:.2f}" if v.f2_ido else '--:--'
                hiba_str = str(v.f2_ossz_hiba) if not v.f2_statusz else v.f2_statusz
                adatok.append([str(idx), str(v.startszam), v.nev, v.nemzetiseg, hiba_str, ido_str])
            
            if len(adatok) > 1:
                table = Table(adatok, colWidths=[40, 60, 140, 60, 60, 70])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.orange),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                story.append(table)
                story.append(Spacer(1, 15))
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'eredmenyek_{verseny.nev}_{verseny.datum}.pdf',
            mimetype='application/pdf'
        )
    except Exception as e:
        return str(e), 500

# ==================== INDÍTÁS ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)