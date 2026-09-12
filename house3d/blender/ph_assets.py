import bpy, json, urllib.request, urllib.parse, pathlib, math
from mathutils import Vector

UA = "House3D-FreePipeline/1.0 (Poly Haven assets)"

def http_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=90) as r:return json.load(r)

def download(url,path):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.stat().st_size>1024:return path
    print('DOWNLOAD',url)
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=180) as r,open(path,'wb') as f:
        while True:
            b=r.read(1024*1024)
            if not b:break
            f.write(b)
    return path

def flatten(node,trail=()):
    if isinstance(node,dict):
        if 'url' in node and isinstance(node['url'],str):yield trail,node
        for k,v in node.items():
            if k!='include':yield from flatten(v,trail+(str(k),))
    elif isinstance(node,list):
        for i,v in enumerate(node):yield from flatten(v,trail+(str(i),))

def included_records(node):
    out=[]
    def rec(x):
        if isinstance(x,dict):
            if 'url' in x and isinstance(x['url'],str):out.append(x)
            for v in x.values():rec(v)
        elif isinstance(x,list):
            for v in x:rec(v)
    rec(node.get('include',{}));return out

def polyhaven_texture(slug,name,cache,scale=1.0):
    files=http_json(f'https://api.polyhaven.com/files/{slug}');records=list(flatten(files))
    def pick(kind):
        best=None
        for trail,r in records:
            p='/'.join(trail).lower();u=r['url'].lower()
            if not (u.endswith('.jpg') or u.endswith('.png')):continue
            good=kind in p or kind in u
            if kind=='nor_gl':good=('nor_gl' in p or 'nor_gl' in u or ('normal' in p and 'dx' not in p))
            if not good:continue
            score=80 if '1k' in p or '/1k/' in u else 60 if '2k' in p or '/2k/' in u else 20
            if best is None or score>best[0]:best=(score,r)
        return best[1] if best else None
    ad=pathlib.Path(cache)/slug;ad.mkdir(parents=True,exist_ok=True);paths={}
    for key in ('diff','rough','nor_gl'):
        rec=pick(key)
        if rec:
            ext=pathlib.Path(urllib.parse.urlparse(rec['url']).path).suffix
            paths[key]=download(rec['url'],ad/f'{key}{ext}')
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear()
    out=nt.nodes.new('ShaderNodeOutputMaterial');bs=nt.nodes.new('ShaderNodeBsdfPrincipled');nt.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    tc=nt.nodes.new('ShaderNodeTexCoord');mp=nt.nodes.new('ShaderNodeMapping');nt.links.new(tc.outputs['UV'],mp.inputs['Vector']);mp.inputs['Scale'].default_value=(scale,scale,scale)
    if 'diff' in paths:
        im=bpy.data.images.load(str(paths['diff']));n=nt.nodes.new('ShaderNodeTexImage');n.image=im;nt.links.new(mp.outputs['Vector'],n.inputs['Vector']);nt.links.new(n.outputs['Color'],bs.inputs['Base Color'])
    if 'rough' in paths:
        im=bpy.data.images.load(str(paths['rough']));im.colorspace_settings.name='Non-Color';n=nt.nodes.new('ShaderNodeTexImage');n.image=im;nt.links.new(mp.outputs['Vector'],n.inputs['Vector']);nt.links.new(n.outputs['Color'],bs.inputs['Roughness'])
    if 'nor_gl' in paths:
        im=bpy.data.images.load(str(paths['nor_gl']));im.colorspace_settings.name='Non-Color';n=nt.nodes.new('ShaderNodeTexImage');n.image=im;nt.links.new(mp.outputs['Vector'],n.inputs['Vector']);nm=nt.nodes.new('ShaderNodeNormalMap');nm.inputs['Strength'].default_value=.45;nt.links.new(n.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],bs.inputs['Normal'])
    return m

def import_polyhaven(slug,name,pos,target,rot,cache):
    print('ASSET',slug)
    try:
        files=http_json(f'https://api.polyhaven.com/files/{slug}');c=[]
        for trail,rec in flatten(files):
            u=rec['url'].lower();p='/'.join(trail).lower()
            if u.endswith('.gltf') or u.endswith('.glb'):
                score=100 if '1k' in p or '/1k/' in u else 70 if '2k' in p or '/2k/' in u else 20
                c.append((score,rec))
        if not c:raise RuntimeError('no glTF variant')
        c.sort(key=lambda x:x[0],reverse=True);rec=c[0][1];ad=pathlib.Path(cache)/slug;ad.mkdir(parents=True,exist_ok=True)
        main=download(rec['url'],ad/pathlib.Path(urllib.parse.urlparse(rec['url']).path).name)
        for dep in included_records(rec):
            u=dep['url'];download(u,ad/pathlib.Path(urllib.parse.urlparse(u).path).name)
        before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(main));objs=[o for o in bpy.data.objects if o not in before]
        if not objs:raise RuntimeError('import empty')
        root=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(root)
        for o in objs:
            if o.parent is None:o.parent=root
        root.rotation_euler[2]=math.radians(rot);bpy.context.view_layer.update()
        def bounds():
            pts=[]
            for o in objs:
                if hasattr(o,'bound_box'):pts.extend(o.matrix_world@Vector(c) for c in o.bound_box)
            mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)));mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)));return mn,mx
        mn,mx=bounds();size=mx-mn;s=min(target[0]/max(size.x,.001),target[1]/max(size.y,.001),target[2]/max(size.z,.001));root.scale=(s,s,s);bpy.context.view_layer.update();mn,mx=bounds();center=(mn+mx)/2
        root.location.x+=pos[0]-center.x;root.location.y+=pos[1]-center.y;root.location.z+=pos[2]-mn.z
        return root
    except Exception as e:
        print('ASSET FAILED',slug,repr(e));return None
