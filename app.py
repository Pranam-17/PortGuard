from flask import Flask, request, jsonify, render_template, send_file
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3, csv, math
import numpy as np

app=Flask(__name__)
BASE=Path(__file__).resolve().parent; DATA=BASE/'data'; DATA.mkdir(exist_ok=True)
DB=DATA/'portguard.db'; CSV=DATA/'sensor_readings.csv'

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=conn()
    c.execute('CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,node TEXT,temperature REAL,humidity REAL,pressure REAL,mq135_1 REAL,mq135_2 REAL,air_quality REAL,ph REAL,tds REAL,turbidity REAL,water_temperature REAL,wqi REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,node TEXT,severity TEXT,sensor TEXT,value REAL,message TEXT,acknowledged INTEGER DEFAULT 0)')
    c.commit(); c.close()
    if not CSV.exists():
        with CSV.open('w',newline='',encoding='utf-8') as f: csv.writer(f).writerow(['timestamp','node','temperature','humidity','pressure','mq135_1','mq135_2','air_quality','ph','tds','turbidity','water_temperature','wqi'])

def finite(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except: return None

def iso(): return datetime.now(timezone.utc).isoformat()

def save(node,d):
    fields=['temperature','humidity','pressure','mq135_1','mq135_2','air_quality','ph','tds','turbidity','water_temperature','wqi']
    r={'timestamp':iso(),'node':node}; [r.__setitem__(k,finite(d.get(k))) for k in fields]
    c=conn(); c.execute('INSERT INTO readings(timestamp,node,temperature,humidity,pressure,mq135_1,mq135_2,air_quality,ph,tds,turbidity,water_temperature,wqi) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r[k] for k in ['timestamp','node']+fields)); c.commit(); c.close()
    with CSV.open('a',newline='',encoding='utf-8') as f: csv.writer(f).writerow([r[k] for k in ['timestamp','node']+fields])
    return r

def latest(node):
    c=conn(); r=c.execute('SELECT * FROM readings WHERE node=? ORDER BY id DESC LIMIT 1',(node,)).fetchone(); c.close(); return dict(r) if r else {'node':node,'timestamp':None}

def add_alert(node,sensor,value,severity,msg):
    c=conn(); cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat(); old=c.execute('SELECT id FROM alerts WHERE node=? AND sensor=? AND severity=? AND timestamp>? LIMIT 1',(node,sensor,severity,cutoff)).fetchone()
    if not old: c.execute('INSERT INTO alerts(timestamp,node,severity,sensor,value,message) VALUES(?,?,?,?,?,?)',(iso(),node,severity,sensor,value,msg)); c.commit()
    c.close()

def check_alerts(r):
    if r['node']=='air':
        q=r.get('air_quality')
        if q is not None:
            if q>300:add_alert('air','air_quality',q,'CRITICAL','Severe air pollution detected')
            elif q>200:add_alert('air','air_quality',q,'HIGH','High air pollution detected')
            elif q>100:add_alert('air','air_quality',q,'MODERATE','Air pollution is increasing')
    else:
        p,t,u=r.get('ph'),r.get('tds'),r.get('turbidity')
        if p is not None and (p<6.5 or p>8.5):add_alert('water','pH',p,'HIGH','Water pH is outside the prototype range')
        if t is not None and t>500:add_alert('water','TDS',t,'HIGH','TDS level is elevated')
        if u is not None:
            if u>50:add_alert('water','turbidity',u,'CRITICAL','Very high turbidity detected')
            elif u>20:add_alert('water','turbidity',u,'HIGH','Turbidity is increasing')

def trend():
    c=conn(); rows=list(reversed(c.execute('SELECT timestamp,ph,tds,turbidity,water_temperature FROM readings WHERE node="water" ORDER BY id DESC LIMIT 300').fetchall())); c.close()
    if len(rows)<8:return {'status':'waiting','samples':len(rows),'message':'Collect at least 8 water readings to activate the trend model.'}
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.ensemble import IsolationForest
    except Exception:return {'status':'error','message':'Install scikit-learn to activate the ML trend engine.'}
    x=np.arange(len(rows)).reshape(-1,1); out={'status':'active','samples':len(rows),'parameters':{}}; worsening=0
    for k in ['ph','tds','turbidity','water_temperature']:
        y=np.array([r[k] if r[k] is not None else np.nan for r in rows],float); mask=np.isfinite(y)
        if mask.sum()<8:out['parameters'][k]={'direction':'insufficient'}; continue
        xx=x[mask]; yy=y[mask]; model=LinearRegression().fit(xx,yy); slope=float(model.coef_[0]); change=float(yy[-1]-yy[0]); pct=float(change/yy[0]*100) if yy[0]!=0 else None
        direction='increasing' if slope>0.001 else 'decreasing' if slope<-0.001 else 'stable'
        iso=IsolationForest(random_state=42,contamination='auto').fit(yy.reshape(-1,1)); anomaly=bool(iso.predict(yy[-1:].reshape(-1,1))[0]==-1)
        out['parameters'][k]={'direction':direction,'slope_per_reading':slope,'change':change,'percent_change':pct,'current':float(yy[-1]),'anomaly':anomaly}
        if (k=='turbidity' and direction=='increasing') or (k=='tds' and direction=='increasing') or (k=='ph' and direction=='decreasing'):worsening+=1
    out['overall']='worsening' if worsening>=2 else ('improving' if worsening==0 else 'mixed'); out['note']="Model analyzes this project's collected water history; it does not measure the entire ocean."; return out

@app.get('/')
def index(): return render_template('index.html')
@app.get('/api/air')
def api_air(): return jsonify({'status':'success','data':latest('air')})
@app.get('/api/water')
def api_water(): return jsonify({'status':'success','data':latest('water')})
@app.post('/api/air')
def post_air():
    d=request.get_json(silent=True)
    if not isinstance(d,dict): return jsonify({'status':'error','error':'Request body must be a JSON object'}),400
    req=['temperature','humidity','pressure','mq135_1','mq135_2','air_quality']; missing=[k for k in req if k not in d]
    if missing:return jsonify({'status':'error','missing':missing}),400
    r=save('air',d); check_alerts(r); return jsonify({'status':'success','data':r}),201
@app.post('/api/water')
def post_water():
    d=request.get_json(silent=True)
    if not isinstance(d,dict): return jsonify({'status':'error','error':'Request body must be a JSON object'}),400
    req=['ph','tds','turbidity','water_temperature']; missing=[k for k in req if k not in d]
    if missing:return jsonify({'status':'error','missing':missing}),400
    r=save('water',d); check_alerts(r); return jsonify({'status':'success','data':r}),201
@app.post('/sensor-data')
def legacy_post():
    d=request.get_json(silent=True) or {}; return post_water() if d.get('node')=='water' else post_air()
@app.get('/sensor-data')
def legacy_get(): return jsonify({'status':'success','air':latest('air'),'water':latest('water'),'trend':trend()})
@app.get('/api/history')
def history():
    node=request.args.get('node'); limit=min(int(request.args.get('limit',300)),1000); c=conn()
    rows=c.execute('SELECT * FROM readings WHERE node=? ORDER BY id DESC LIMIT ?',(node,limit)).fetchall() if node in ['air','water'] else c.execute('SELECT * FROM readings ORDER BY id DESC LIMIT ?',(limit,)).fetchall(); c.close(); return jsonify({'readings':[dict(r) for r in reversed(rows)]})
@app.get('/api/trends')
def trends(): return jsonify(trend())
@app.get('/alerts/recent')
def alerts():
    c=conn(); rows=c.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT 30').fetchall(); c.close(); return jsonify({'alerts':[dict(r) for r in rows]})
@app.post('/alerts/acknowledge/<int:i>')
def ack(i):
    c=conn(); c.execute('UPDATE alerts SET acknowledged=1 WHERE id=?',(i,)); c.commit(); c.close(); return jsonify({'status':'success'})
@app.get('/reports/summary')
def summary():
    c=conn(); s={k:c.execute(q).fetchone()[0] for k,q in {'records':'SELECT COUNT(*) FROM readings','air_records':'SELECT COUNT(*) FROM readings WHERE node="air"','water_records':'SELECT COUNT(*) FROM readings WHERE node="water"','alerts':'SELECT COUNT(*) FROM alerts'}.items()}; c.close(); return jsonify({'summary':s,'trend':trend()})
@app.get('/reports/csv')
def csv_report(): return send_file(CSV,as_attachment=True,download_name='portguard_sensor_readings.csv')
@app.get('/reports/excel')
def excel_report():
    from openpyxl import Workbook
    c=conn(); rows=c.execute('SELECT * FROM readings ORDER BY id').fetchall(); c.close(); wb=Workbook(); ws=wb.active; ws.title='Sensor Readings'; ws.append(list(rows[0].keys()) if rows else ['No data']); [ws.append(list(r)) for r in rows]; path=DATA/'portguard_report.xlsx'; wb.save(path); return send_file(path,as_attachment=True,download_name='portguard_report.xlsx')
init()
if __name__=='__main__':
    print('SMART PORTGUARD — REAL-TIME DASHBOARD'); print('Open http://localhost:5001'); print('Air: http://<LAPTOP-IP>:5001/api/air'); print('Water: http://<LAPTOP-IP>:5001/api/water'); app.run(host='0.0.0.0',port=5001,debug=True)
