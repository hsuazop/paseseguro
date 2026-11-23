import openpyxl, os, re, json, unicodedata, difflib, math
from collections import defaultdict, Counter

files={
'recibos':r'C:\Users\hecto\Mi unidad\villa olimpica\Entrega de vicenta\RECIBOS PROGRAMA VEHICULAR 2026.xlsx',
'actas':r'C:\Users\hecto\Mi unidad\villa olimpica\Entrega de vicenta\ACTAS CLAVES CATATRAL VILLA OLIMPICA.xlsx',
'censo':r'C:\Users\hecto\Mi unidad\villa olimpica\Entrega de vicenta\CENSO.xlsx',
'vehiculos':r'C:\Users\hecto\Mi unidad\villa olimpica\Entrega de vicenta\INFORMACION VEHICULAR SECTOR 1.xlsx',
'pagos':r'C:\Users\hecto\Mi unidad\villa olimpica\Entrega de vicenta\PAGO VIGILANCIA SECTOR1 2026.xlsx',
}

def clean(v):
 if v is None: return ''
 if isinstance(v,float) and v.is_integer(): return str(int(v))
 return str(v).strip()
def norm_phone(v):
 s=''.join(re.findall(r'\d',clean(v)))
 return s[-8:] if len(s)>=8 else s
def norm_name(v):
 s=clean(v).upper().replace('�','Ñ')
 s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode('ascii')
 s=re.sub(r'[^A-Z0-9 ]+',' ',s)
 s=re.sub(r'\b(DONA|DON|PROF|PROFA|ING|LIC|DR|DRA)\b',' ',s)
 s=re.sub(r'\s+',' ',s).strip()
 return s

def rowdict(headers,row):
 return {clean(h): (row[i] if i<len(row) else None) for i,h in enumerate(headers)}
records=[]
# recibos vecinos
wb=openpyxl.load_workbook(files['recibos'],data_only=True,read_only=True)
ws=wb['vecinos']; headers=[clean(x.value) for x in ws[2]]
for rn,row in enumerate(ws.iter_rows(min_row=3,values_only=True),3):
 d=rowdict(headers,row); name=d.get('NOMBRE VECINO')
 if clean(name): records.append({'source':'RECIBOS vecinos','row':rn,'name':clean(name),'phone':norm_phone(d.get('CELULAR')),'sector':'1','block':clean(d.get('BLOQUE')),'house':clean(d.get('CASA')),'vehicle1':clean(d.get('MARCA'))+' '+clean(d.get('MODELO')),'vehicle2':clean(d.get('MARCA2'))+' '+clean(d.get('MODELO2')),'plate':clean(d.get('PLACA')),'cadastral':'','notes':''})
# actas sectors
wb=openpyxl.load_workbook(files['actas'],data_only=True,read_only=True)
for s in ['SECTOR 1','SECTOR 2','SECTOR 3']:
 ws=wb[s]; start=2 if s!='SECTOR 3' else 3; headers=[clean(x.value) for x in ws[start]]
 for rn,row in enumerate(ws.iter_rows(min_row=start+1,values_only=True),start+1):
  d=rowdict(headers,row); name=d.get('RESIDENTE')
  if clean(name): records.append({'source':'ACTAS '+s,'row':rn,'name':clean(name),'phone':norm_phone(d.get('TELEFONO')),'sector':clean(d.get('SEC')) or s[-1],'block':clean(d.get('BL')),'house':clean(d.get('C#')),'vehicle1':'','vehicle2':'','plate':'','cadastral':clean(d.get('CLAVE CATASTRAL')),'notes':clean(d.get('OBSE'))})
# censo
wb=openpyxl.load_workbook(files['censo'],data_only=True,read_only=True); ws=wb['Hoja1']; headers=[clean(x.value) for x in ws[1]]
for rn,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
 d=rowdict(headers,row); name=d.get('Nombre Responsable del Hogar')
 if clean(name): records.append({'source':'CENSO','row':rn,'name':clean(name),'phone':norm_phone(d.get('Tel�fono')) or norm_phone(d.get('Teléfono')),'sector':clean(d.get('Sector')),'block':clean(d.get('Bloque')),'house':clean(d.get('N�mero de Casa')) or clean(d.get('Número de Casa')),'vehicle1':clean(d.get('Cantidad de autom�viles en el hogar')),'vehicle2':'','plate':'','cadastral':'','notes':'Habitantes: '+clean(d.get('Cantidad de Habitantes en el Hogar'))})
# vehiculos sheet1
wb=openpyxl.load_workbook(files['vehiculos'],data_only=True,read_only=True); ws=wb['Hoja1']; headers=[clean(x.value) for x in ws[1]]
for rn,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
 d=rowdict(headers,row); name=d.get('NOMBRE PROPIETARIO')
 if clean(name): records.append({'source':'VEHICULOS Hoja1','row':rn,'name':clean(name),'phone':norm_phone(d.get('CELULAR')),'sector':'1','block':'','house':'','vehicle1':clean(d.get('MODELO/MARCA')),'vehicle2':'','plate':clean(d.get('PLACA'))+' '+clean(d.get('None')),'cadastral':'','notes':clean(d.get('COLOR'))})
# vehiculos sheet2
ws=wb['Hoja2']; headers=[clean(x.value) for x in ws[1]]
for rn,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
 d=rowdict(headers,row); name=d.get('Nombre')
 if clean(name): records.append({'source':'VEHICULOS Hoja2','row':rn,'name':clean(name),'phone':norm_phone(d.get('Tel�fono')) or norm_phone(d.get('Teléfono')),'sector':'1','block':'','house':'','vehicle1':clean(d.get('Placa / Veh�culo')) or clean(d.get('Placa / Vehículo')),'vehicle2':'','plate':clean(d.get('Placa / Veh�culo')) or clean(d.get('Placa / Vehículo')),'cadastral':'','notes':clean(d.get('Apartamento / Observaciones'))})
# payment validation
wbp=openpyxl.load_workbook(files['pagos'],data_only=True,read_only=True); ws=wbp['DATOS PARA VALID']; headers=[clean(x.value) for x in ws[1]]; payment_valid=[]
for rn,row in enumerate(ws.iter_rows(min_row=2,values_only=True),2):
 d=rowdict(headers,row); name=d.get('VECINO CONTRIBUYENTE SEGURIDAD 2026')
 if clean(name):
  p={'source':'PAGOS DATOS PARA VALID','row':rn,'name':clean(name),'phone':norm_phone(d.get('TEL')),'sector':'1','block':'','house':'','vehicle1':'','vehicle2':'','plate':'','cadastral':'','notes':'Forma: '+clean(d.get('FORMA DE PAGO'))}
  records.append(p); payment_valid.append(p)
# monthly payments, parse header row containing vec/amount, use data_only
payrows=[]
for ws in wbp.worksheets:
 if ws.title in ['HOJA GENERAL','DATOS PARA VALID']: continue
 header_row=None; headers=None
 for rr in range(1,min(ws.max_row,8)+1):
  vals=[clean(x.value) for x in ws[rr]]
  if any('VECINO' in x.upper() for x in vals) and any('MONTO' in x.upper() for x in vals): header_row=rr; headers=vals; break
 if not header_row: continue
 name_idx=next((i for i,x in enumerate(headers) if 'VECINO' in x.upper()),None)
 amt_idx=next((i for i,x in enumerate(headers) if 'MONTO' in x.upper()),None)
 if name_idx is None or amt_idx is None: continue
 for rn,row in enumerate(ws.iter_rows(min_row=header_row+1,values_only=True),header_row+1):
  name=clean(row[name_idx] if name_idx<len(row) else None)
  if not name: continue
  amt=row[amt_idx] if amt_idx<len(row) else None
  try: amount=float(amt) if amt not in (None,'') else 0
  except: amount=0
  if not amount: continue
  concept=''
  # nearby concept field
  for i,x in enumerate(headers):
   if 'CONCEPTO' in x.upper() and i<len(row): concept=clean(row[i])
  payrows.append({'sheet':ws.title,'row':rn,'name':name,'name_norm':norm_name(name),'amount':amount,'concept':concept})
# matching summaries
by_phone=defaultdict(list); by_name=defaultdict(list)
for r in records:
 r['name_norm']=norm_name(r['name']); r['phone_norm']=r['phone']
 if r['phone_norm']: by_phone[r['phone_norm']].append(r)
 if r['name_norm']: by_name[r['name_norm']].append(r)
# canonical clusters by phone only. Records without phone stay separate.
clusters=[]; assigned=set()
for p,items in by_phone.items():
 ids=set(id(x) for x in items); clusters.append(('phone',p,items)); assigned |= ids
for r in records:
 if id(r) not in assigned: clusters.append(('single',str(id(r)),[r]))
# payment aggregate by normalized name
payagg=defaultdict(lambda:{'total':0,'count':0,'months':set(),'rows':[]})
for p in payrows:
 a=payagg[p['name_norm']]; a['total']+=p['amount']; a['count']+=1; a['months'].add(p['sheet']); a['rows'].append(p['row'])
# compute clusters output
out=[]; conflicts=[]
for idx,(kind,key,items) in enumerate(clusters,1):
 phones=sorted({x['phone_norm'] for x in items if x['phone_norm']}); names=sorted({x['name'] for x in items if x['name']},key=len)
 n_norms={x['name_norm'] for x in items if x['name_norm']}
 # choose most common/longest clean name
 cname=max(names,key=lambda x:(len(x),x)) if names else ''
 # choose fields from first nonblank, prefer source order recibos/actas/censo
 def first(field):
  for x in items:
   if clean(x.get(field)): return clean(x.get(field))
  return ''
 payment_candidates=[]
 for pn,a in payagg.items():
  ratio=difflib.SequenceMatcher(None,pn,norm_name(cname)).ratio()
  if pn==norm_name(cname) or ratio>=0.92: payment_candidates.append((ratio,pn,a))
 payment_candidates.sort(reverse=True)
 pa=payment_candidates[0][2] if payment_candidates else {'total':0,'count':0,'months':set(),'rows':[]}
 status='COINCIDE CELULAR' if kind=='phone' else ('SIN CELULAR - REVISAR' if not phones else 'REGISTRO ÚNICO')
 if len(phones)>1:
  status='CONFLICTO: MÁS DE UN CELULAR'; conflicts.append((idx,'El mismo nombre aparece con varios celulares',phones,names))
 if kind=='phone' and len(n_norms)>1: conflicts.append((idx,'El mismo celular aparece con nombres distintos',phones,names))
 out.append({'id':f'P-{idx:04d}','nombre_canonico':cname,'celular':phones[0] if len(phones)==1 else (phones[0] if phones else ''),'celulares_detectados':' | '.join(phones),'nombres_detectados':' | '.join(names),'sector':first('sector'),'bloque':first('block'),'casa':first('house'),'clave_catastral':first('cadastral'),'vehiculo':'; '.join(sorted({clean(x.get('vehicle1')) for x in items if clean(x.get('vehicle1'))})),'placa':'; '.join(sorted({clean(x.get('plate')) for x in items if clean(x.get('plate'))})),'observaciones':' | '.join(sorted({clean(x.get('notes')) for x in items if clean(x.get('notes'))})),'fuentes':' | '.join(sorted({x['source'] for x in items})),'estado_consolidacion':status,'registros_origen':len(items),'pago_total_2026':pa['total'],'pagos_registrados':pa['count'],'meses_con_pago':' | '.join(sorted(pa['months']))})
# Exact same name with no phone is a review case, not an automatic merge.
no_phone_by_name=defaultdict(list)
for o in out:
 if not o['celular'] and norm_name(o['nombre_canonico']): no_phone_by_name[norm_name(o['nombre_canonico'])].append(o)
for n,items in no_phone_by_name.items():
 if len(items)>1:
  for o in items: o['estado_consolidacion']='NOMBRE REPETIDO SIN CELULAR'
  conflicts.append((", ".join(o['id'] for o in items),'Nombre exacto repetido sin celular',[],[o['nombre_canonico'] for o in items]))
# potential fuzzy name matches across different phone records
name_to_clusters=defaultdict(list)
for i,o in enumerate(out): name_to_clusters[norm_name(o['nombre_canonico'])].append(i)
fuzzy=[]
for i,a in enumerate(out):
 for j in range(i+1,len(out)):
  b=out[j]; na=norm_name(a['nombre_canonico']); nb=norm_name(b['nombre_canonico'])
  if not na or not nb or na==nb: continue
  ratio=difflib.SequenceMatcher(None,na,nb).ratio()
  if ratio>=0.86 and (a['celular']!=b['celular']): fuzzy.append({'registro1':a['id'],'nombre1':a['nombre_canonico'],'celular1':a['celular'],'registro2':b['id'],'nombre2':b['nombre_canonico'],'celular2':b['celular'],'similitud':round(ratio,3),'accion':'REVISAR SI ES LA MISMA PERSONA'})
# detailed source rows output
for r in records: r.pop('name_norm',None); r.pop('phone_norm',None)
summary={'source_counts':Counter(r['source'] for r in records),'raw_records':len(records),'clusters':len(out),'clusters_with_phone':sum(bool(x['celular']) for x in out),'clusters_without_phone':sum(not x['celular'] for x in out),'conflicts':len(conflicts),'fuzzy':len(fuzzy),'payment_rows':len(payrows)}
json.dump({'records':out,'conflicts':[{'registro':x[0],'tipo':x[1],'celulares':' | '.join(x[2]),'nombres':' | '.join(x[3])} for x in conflicts],'fuzzy':fuzzy,'summary':summary,'payment_detail':payrows},open(r'C:\dev\django\proyectos\paseseguro\consolidado_data.json','w',encoding='utf-8'),ensure_ascii=False,default=list,indent=2)
print(json.dumps(summary,ensure_ascii=False))
print('conflicts sample',json.dumps([{'registro':x[0],'tipo':x[1],'celulares':x[2],'nombres':x[3]} for x in conflicts[:10]],ensure_ascii=False))
print('fuzzy sample',json.dumps(fuzzy[:10],ensure_ascii=False))
