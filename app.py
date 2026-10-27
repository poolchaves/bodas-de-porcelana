import os, csv, io, secrets, re
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo
from urllib.parse import quote
from flask import Flask, request, session, redirect, url_for, render_template_string, flash, Response, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
import qrcode

TZ = ZoneInfo('America/Porto_Velho')
DEADLINE = datetime(2026, 11, 1, 23, 59, 59, tzinfo=TZ)
MAPS = 'https://maps.google.com/?q=-8.769730,-63.876278'
ACCESS = 'https://app.qrtoken.com.br/evento/?codigo=Njg3MTYsMTAyMCwyMDI2LTEwLTI3IDEzOjA3OjA4'
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'DEV_ONLY_REPLACE_BEFORE_DEPLOY')
if os.environ.get('RENDER') and (not os.environ.get('SECRET_KEY') or not (os.environ.get('ADMIN_PASSWORD') or os.environ.get('ADMIN_PASSWORD_HASH'))):
    raise RuntimeError('Configure SECRET_KEY e ADMIN_PASSWORD (ou ADMIN_PASSWORD_HASH) antes de publicar.')
db_url = os.environ.get('DATABASE_URL', 'sqlite:///bodas.db')
if db_url.startswith('postgres://'): db_url = db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1'
app.config['MAX_CONTENT_LENGTH'] = 1_000_000
app.config['PREFERRED_URL_SCHEME'] = 'https'
db = SQLAlchemy(app)

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first = db.Column(db.String(100), nullable=False)
    second = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(12), nullable=False, default='pendente')
    people = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

with app.app_context(): db.create_all()

def csrf_token():
    if '_csrf' not in session: session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']
app.jinja_env.globals['csrf_token'] = csrf_token

def verify_csrf():
    if not secrets.compare_digest(request.form.get('csrf', ''), session.get('_csrf', '')): abort(400, 'Sessão expirada ou formulário inválido. Atualize a página.')

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get('admin'): return redirect(url_for('login', next=request.path))
        return fn(*a, **kw)
    return wrapper

def now_local(): return datetime.now(TZ)
def open_rsvp(): return now_local() <= DEADLINE

def base_html(body, **ctx):
    template = '''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#102b4d"><title>{{ title or 'Bodas de Porcelana' }}</title><link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}"></head><body><main class="page">{% with msgs=get_flashed_messages() %}{% if msgs %}<div class="flash">{% for m in msgs %}<p>{{m}}</p>{% endfor %}</div>{% endif %}{% endwith %}''' + body + '''</main></body></html>'''
    return render_template_string(template, **ctx)

@app.get('/')
def home():
    return redirect(url_for('admin') if session.get('admin') else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        verify_csrf()
        pw = os.environ.get('ADMIN_PASSWORD', '')
        hashed = os.environ.get('ADMIN_PASSWORD_HASH', '')
        valid = bool(hashed and check_password_hash(hashed, request.form.get('password', ''))) or bool(pw and secrets.compare_digest(pw, request.form.get('password', '')))
        if valid:
            session.clear(); session['admin'] = True; csrf_token()
            return redirect(url_for('admin'))
        flash('Senha incorreta.')
    return base_html('''<section class="panel narrow"><p class="eyebrow">ÁREA RESTRITA</p><h1>Painel dos convidados</h1><p>Marcelle & Paulo · Bodas de Porcelana</p><form method="post"><input type="hidden" name="csrf" value="{{csrf_token()}}"><label>Senha administrativa<input type="password" name="password" autocomplete="current-password" required></label><button class="btn" type="submit">Entrar</button></form></section>''')

@app.post('/logout')
@admin_required
def logout():
    verify_csrf(); session.clear(); return redirect(url_for('login'))

@app.get('/admin')
@admin_required
def admin():
    guests = Guest.query.order_by(Guest.created_at.desc(), Guest.id.desc()).all()
    yes = [g for g in guests if g.status == 'sim']
    return base_html('''<header class="admin-head"><div><p class="eyebrow">PAINEL ADMINISTRATIVO</p><h1>Bodas de Porcelana</h1><p>Marcelle e Paulo Chaves · 28/11/2026 · 17h</p></div><form action="{{url_for('logout')}}" method="post"><input type="hidden" name="csrf" value="{{csrf_token()}}"><button class="btn outline">Sair</button></form></header><section class="stats"><div><strong>{{guests|length}}</strong><span>Casais convidados</span></div><div><strong>{{yes|length}}</strong><span>Convites confirmados</span></div><div><strong>{{yes|sum(attribute='people')}}</strong><span>Pessoas confirmadas</span></div><div><strong>{{guests|selectattr('status','equalto','nao')|list|length}}</strong><span>Recusados</span></div><div><strong>{{guests|selectattr('status','equalto','pendente')|list|length}}</strong><span>Pendentes</span></div></section><section class="panel"><h2>Cadastrar casal</h2><form method="post" action="{{url_for('add_guest')}}" class="add-form"><input type="hidden" name="csrf" value="{{csrf_token()}}"><label>Primeiro convidado<input name="first" maxlength="100" placeholder="João" required></label><label>Segundo convidado<input name="second" maxlength="100" placeholder="Maria" required></label><button class="btn">Gerar convite</button></form></section><section class="panel"><div class="section-head"><h2>Convidados</h2><a class="btn outline" href="{{url_for('export_csv')}}">Exportar CSV</a></div>{% if guests %}<div class="guest-list">{% for g in guests %}{% set link=url_for('invite',token=g.token,_external=True) %}{% set msg='Olá, '+g.first+' e '+g.second+'! Marcelle e Paulo Chaves convidam vocês para celebrar suas Bodas de Porcelana, dia 28 de novembro, às 17h. Vejam os detalhes e confirmem até 1º de novembro: '+link %}<article class="guest"><div><strong>{{g.first}} e {{g.second}}</strong><small>{{ 'Confirmado · '+g.people|string+' pessoa(s)' if g.status=='sim' else 'Não comparecerão' if g.status=='nao' else 'Aguardando resposta' }}</small></div><div class="actions"><a class="mini" href="{{link}}" target="_blank" rel="noopener">Ver convite</a><button class="mini" type="button" onclick="navigator.clipboard.writeText({{link|tojson}}).then(()=>alert('Link copiado!')).catch(()=>prompt('Copie o link:',{{link|tojson}}))">Copiar link</button><a class="mini" href="https://wa.me/?text={{msg|urlencode}}" target="_blank" rel="noopener">WhatsApp</a><a class="mini" href="{{url_for('qr',token=g.token)}}" download="qr-convite-{{g.token}}.png">QR Code</a><form method="post" action="{{url_for('delete_guest',id=g.id)}}" onsubmit="return confirm('Excluir este convite?')"><input type="hidden" name="csrf" value="{{csrf_token()}}"><button class="mini danger">Excluir</button></form></div><form class="edit-form" method="post" action="{{url_for('edit_guest',id=g.id)}}"><input type="hidden" name="csrf" value="{{csrf_token()}}"><input name="first" value="{{g.first}}" maxlength="100" required aria-label="Primeiro nome"><input name="second" value="{{g.second}}" maxlength="100" required aria-label="Segundo nome"><select name="status" aria-label="Resposta"><option value="pendente" {% if g.status=='pendente' %}selected{% endif %}>Pendente</option><option value="sim" {% if g.status=='sim' %}selected{% endif %}>Confirmado</option><option value="nao" {% if g.status=='nao' %}selected{% endif %}>Não vai</option></select><select name="people" aria-label="Pessoas"><option value="1" {% if g.people==1 %}selected{% endif %}>1 pessoa</option><option value="2" {% if g.people==2 %}selected{% endif %}>2 pessoas</option></select><button class="mini" type="submit">Salvar</button></form></article>{% endfor %}</div>{% else %}<p>Nenhum casal cadastrado. Cadastre o primeiro acima.</p>{% endif %}</section>''', guests=guests, yes=yes)

def clean_name(v): return re.sub(r'\s+', ' ', v.strip())[:100]
@app.post('/admin/add')
@admin_required
def add_guest():
    verify_csrf(); first=clean_name(request.form.get('first','')); second=clean_name(request.form.get('second',''))
    if not first or not second: flash('Informe os dois nomes.'); return redirect(url_for('admin'))
    db.session.add(Guest(first=first,second=second,token=secrets.token_urlsafe(12)))
    db.session.commit(); flash('Convite criado! Copie o link ou compartilhe pelo WhatsApp.'); return redirect(url_for('admin'))

@app.post('/admin/edit/<int:id>')
@admin_required
def edit_guest(id):
    verify_csrf(); g=db.get_or_404(Guest,id)
    first=clean_name(request.form.get('first','')); second=clean_name(request.form.get('second',''))
    status=request.form.get('status','pendente'); people=request.form.get('people','1')
    if not first or not second or status not in ('sim','nao','pendente') or people not in ('1','2'): abort(400)
    g.first=first; g.second=second; g.status=status; g.people=int(people) if status=='sim' else 0
    db.session.commit(); flash('Cadastro atualizado.'); return redirect(url_for('admin'))

@app.post('/admin/delete/<int:id>')
@admin_required
def delete_guest(id):
    verify_csrf(); db.session.delete(db.get_or_404(Guest,id)); db.session.commit(); flash('Convite excluído.'); return redirect(url_for('admin'))

@app.get('/admin/export.csv')
@admin_required
def export_csv():
    output=io.StringIO(); output.write('\ufeff'); writer=csv.writer(output)
    writer.writerow(['Primeiro convidado','Segundo convidado','Resposta','Pessoas','Link'])
    for g in Guest.query.order_by(Guest.id).all(): writer.writerow([g.first,g.second,g.status,g.people,url_for('invite',token=g.token,_external=True)])
    return Response(output.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=convidados-bodas.csv'})

@app.route('/c/<token>',methods=['GET','POST'])
def invite(token):
    g=Guest.query.filter_by(token=token).first_or_404()
    if request.method=='POST':
        verify_csrf()
        if not open_rsvp(): flash('O prazo de confirmação terminou.'); return redirect(url_for('invite',token=token))
        status=request.form.get('status',''); people=request.form.get('people','2')
        if status not in ('sim','nao') or (status=='sim' and people not in ('1','2')): abort(400)
        g.status=status; g.people=int(people) if status=='sim' else 0
        db.session.commit(); flash('Sua resposta foi registrada. Obrigado!')
        return redirect(url_for('invite',token=token))
    return base_html('''<section class="invitation"><div class="photo"><img src="{{url_for('static',filename='casal.png')}}" alt="Marcelle e Paulo Chaves"><div class="photo-text"><p>20 ANOS DE CASAMENTO</p><h1>Bodas de Porcelana</h1><h2>Marcelle & Paulo</h2></div></div><div class="invite-body"><p class="eyebrow">CONVITE ESPECIAL</p><h2>{{g.first}} e {{g.second}}</h2><p>Com muita alegria, convidamos vocês para celebrar conosco nossos 20 anos de casamento!</p><div class="details"><p>📅 <strong>Sábado, 28 de novembro de 2026</strong></p><p>🕔 <strong>17 horas</strong></p><p>📍 <strong>Residencial Ipê</strong><br>Rua Manoel Laurentino de Souza, 768, apartamento 805, bairro Nova Porto Velho, Porto Velho/RO</p><p>👔 <strong>Traje:</strong> Esporte social — venha à vontade.</p></div><div class="link-buttons"><a class="btn" href="{{maps}}" target="_blank" rel="noopener noreferrer">📍 Abrir Google Maps</a><a class="btn outline" href="{{access}}" target="_blank" rel="noopener noreferrer">🔑 Cadastrar acesso ao condomínio</a></div><p class="small-note">O cadastro para entrar no condomínio é independente da confirmação de presença.</p><p class="gift">Gentilmente, não tragam presentes.<br><strong>Sua presença já é o nosso presente!</strong></p><div class="rsvp"><h3>Confirmação de presença</h3>{% if g.status=='sim' %}<p class="success">✓ Presença confirmada: {{g.people}} {{'pessoa' if g.people==1 else 'pessoas'}}.</p><p class="small-note">Lembre-se de cadastrar o acesso ao condomínio.</p>{% elif g.status=='nao' %}<p class="success">Sua resposta foi registrada. Sentiremos sua falta!</p>{% endif %}{% if is_open %}<p class="small-note">Confirme até 1º de novembro de 2026.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf_token()}}"><label class="choice"><input type="radio" name="status" value="sim" {% if g.status!='nao' %}checked{% endif %} required> Confirmo minha presença</label><label class="choice"><input type="radio" name="status" value="nao" {% if g.status=='nao' %}checked{% endif %}> Não poderei comparecer</label><div class="count"><label>Quantas pessoas estarão presentes?<select name="people"><option value="1" {% if g.people==1 %}selected{% endif %}>1 pessoa</option><option value="2" {% if g.people!=1 %}selected{% endif %}>2 pessoas</option></select></label></div><button class="btn" type="submit">{{'Atualizar resposta' if g.status!='pendente' else 'Enviar confirmação'}}</button></form>{% else %}<p class="small-note">O prazo de confirmação foi encerrado. Para alterações, entre em contato com os anfitriões.</p>{% endif %}</div></div></section>''',g=g,maps=MAPS,access=ACCESS,is_open=open_rsvp())

@app.get('/qr/<token>.png')
@admin_required
def qr(token):
    g=Guest.query.filter_by(token=token).first_or_404()
    img=qrcode.make(url_for('invite',token=g.token,_external=True)); stream=io.BytesIO(); img.save(stream,format='PNG'); stream.seek(0)
    return send_file(stream,mimetype='image/png',download_name=f'convite-{g.token}.png',as_attachment=True)

if __name__=='__main__': app.run(debug=os.environ.get('FLASK_DEBUG')=='1')
