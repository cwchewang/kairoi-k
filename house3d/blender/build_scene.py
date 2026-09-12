import bpy, math, pathlib, sys
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
CACHE = ROOT / '.asset_cache'
DIST.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from ph_assets import polyhaven_texture, import_polyhaven

T = 0.12
HEIGHT = 2.80
DOOR_H = 2.10
WIN_SILL = 0.82
WIN_HEAD = 2.22

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def simple_mat(name, color, rough=.55, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    return m

def wall_mat():
    m = bpy.data.materials.new('Warm mineral plaster')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (0.54, 0.51, 0.45, 1)
    bs.inputs['Roughness'].default_value = 0.86
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 55
    noise.inputs['Detail'].default_value = 3
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.10
    bump.inputs['Distance'].default_value = 0.015
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return m

WALL = wall_mat()
WOOD = polyhaven_texture('wooden_floor_02', 'Warm oak floor', CACHE, .72)
STONE = polyhaven_texture('marble_tiles', 'Warm stone tile', CACHE, 1.35)
BAL = simple_mat('Balcony stone', (.34, .35, .34), .82)
FRAME = simple_mat('Window frame', (.055, .06, .065), .24, .68)
TRIM = simple_mat('Door trim', (.78, .75, .68), .56)
CAB = simple_mat('Cabinet oak', (.36, .20, .10), .40)
COUNTER = simple_mat('Countertop', (.28, .27, .25), .28)
TV = simple_mat('Display black', (.012, .016, .020), .16)
METAL = simple_mat('Brushed metal', (.34, .36, .38), .28, .72)
RUG = simple_mat('Rug', (.43, .39, .34), .94)

GLASS = bpy.data.materials.new('Architectural glass')
GLASS.use_nodes = True
bs = GLASS.node_tree.nodes.get('Principled BSDF')
bs.inputs['Base Color'].default_value = (.55, .72, .82, 1)
bs.inputs['Roughness'].default_value = .08
(bs.inputs.get('Transmission Weight') or bs.inputs.get('Transmission')).default_value = .86
bs.inputs['IOR'].default_value = 1.45

def add_uv(mesh, tile=1.0):
    uv = mesh.uv_layers.new(name='UVMap')
    for li, loop in enumerate(mesh.loops):
        v = mesh.vertices[loop.vertex_index].co
        uv.data[li].uv = (v.x / tile, v.y / tile)

def floor_obj(name, pts, material, z=.01):
    mesh = bpy.data.meshes.new(name + 'Mesh')
    mesh.from_pydata([(x, y, z) for x, y in pts], [], [list(range(len(pts)))])
    mesh.update()
    add_uv(mesh, 1.1)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj

def box(name, loc, size, material, bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    if bevel:
        mod = o.modifiers.new('micro bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
    return o

def add_box_tuple(out, xmin, xmax, ymin, ymax, zmin, zmax):
    if xmax-xmin > 1e-5 and ymax-ymin > 1e-5 and zmax-zmin > 1e-5:
        out.append(tuple(round(v, 6) for v in (xmin,xmax,ymin,ymax,zmin,zmax)))

def wallrun_boxes(out, x1, y1, x2, y2, openings=()):
    vertical = abs(x2-x1) < 1e-7
    L = abs((y2-y1) if vertical else (x2-x1))
    start = min(y1,y2) if vertical else min(x1,x2)
    const = x1 if vertical else y1
    cur = 0.0
    def seg(a,b,z0=0,z1=HEIGHT):
        if b-a <= 1e-5: return
        if vertical:
            add_box_tuple(out, const-T/2, const+T/2, start+a, start+b, z0, z1)
        else:
            add_box_tuple(out, start+a, start+b, const-T/2, const+T/2, z0, z1)
    for a,b,k in sorted(openings):
        seg(cur,a)
        if k == 'window':
            seg(a,b,0,WIN_SILL)
            seg(a,b,WIN_HEAD,HEIGHT)
        else:
            seg(a,b,DOOR_H,HEIGHT)
        cur = b
    seg(cur,L)

def fused_boxes_mesh(name, boxes, material):
    xs = sorted(set(v for b in boxes for v in (b[0],b[1])))
    ys = sorted(set(v for b in boxes for v in (b[2],b[3])))
    zs = sorted(set(v for b in boxes for v in (b[4],b[5])))
    occ = set()
    for i in range(len(xs)-1):
        cx=(xs[i]+xs[i+1])/2
        for j in range(len(ys)-1):
            cy=(ys[j]+ys[j+1])/2
            for k in range(len(zs)-1):
                cz=(zs[k]+zs[k+1])/2
                if any(b[0]-1e-7<=cx<=b[1]+1e-7 and b[2]-1e-7<=cy<=b[3]+1e-7 and b[4]-1e-7<=cz<=b[5]+1e-7 for b in boxes):
                    occ.add((i,j,k))
    verts=[]; faces=[]; vid={}
    def v(x,y,z):
        key=(round(x,6),round(y,6),round(z,6))
        if key not in vid:
            vid[key]=len(verts); verts.append(key)
        return vid[key]
    for i,j,k in occ:
        x0,x1=xs[i],xs[i+1]; y0,y1=ys[j],ys[j+1]; z0,z1=zs[k],zs[k+1]
        if (i-1,j,k) not in occ: faces.append([v(x0,y0,z0),v(x0,y0,z1),v(x0,y1,z1),v(x0,y1,z0)])
        if (i+1,j,k) not in occ: faces.append([v(x1,y0,z0),v(x1,y1,z0),v(x1,y1,z1),v(x1,y0,z1)])
        if (i,j-1,k) not in occ: faces.append([v(x0,y0,z0),v(x1,y0,z0),v(x1,y0,z1),v(x0,y0,z1)])
        if (i,j+1,k) not in occ: faces.append([v(x0,y1,z0),v(x0,y1,z1),v(x1,y1,z1),v(x1,y1,z0)])
        if (i,j,k-1) not in occ: faces.append([v(x0,y0,z0),v(x0,y1,z0),v(x1,y1,z0),v(x1,y0,z0)])
        if (i,j,k+1) not in occ: faces.append([v(x0,y0,z1),v(x1,y0,z1),v(x1,y1,z1),v(x0,y1,z1)])
    mesh=bpy.data.meshes.new(name+'Mesh')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    bevel=obj.modifiers.new('edge softness','BEVEL');bevel.width=.008;bevel.segments=2
    return obj

def window(name, x, y, w, axis='x'):
    f=.045; d=.075; h=WIN_HEAD-WIN_SILL
    if axis=='x':
        box(name+'Glass',(x,y,(WIN_SILL+WIN_HEAD)/2),(w-.09,.018,h-.09),GLASS,.002)
        box(name+'L',(x-w/2+f/2,y,(WIN_SILL+WIN_HEAD)/2),(f,d,h),FRAME,.003)
        box(name+'R',(x+w/2-f/2,y,(WIN_SILL+WIN_HEAD)/2),(f,d,h),FRAME,.003)
        box(name+'T',(x,y,WIN_HEAD-f/2),(w,d,f),FRAME,.003)
        box(name+'B',(x,y,WIN_SILL+f/2),(w,d,f),FRAME,.003)
    else:
        box(name+'Glass',(x,y,(WIN_SILL+WIN_HEAD)/2),(.018,w-.09,h-.09),GLASS,.002)
        box(name+'L',(x,y-w/2+f/2,(WIN_SILL+WIN_HEAD)/2),(d,f,h),FRAME,.003)
        box(name+'R',(x,y+w/2-f/2,(WIN_SILL+WIN_HEAD)/2),(d,f,h),FRAME,.003)
        box(name+'T',(x,y,WIN_HEAD-f/2),(d,w,f),FRAME,.003)
        box(name+'B',(x,y,WIN_SILL+f/2),(d,w,f),FRAME,.003)

def doorframe(name,x,y,w,axis='x'):
    f=.045; d=.085
    if axis=='x':
        box(name+'L',(x-w/2,y,DOOR_H/2),(f,d,DOOR_H),TRIM,.003)
        box(name+'R',(x+w/2,y,DOOR_H/2),(f,d,DOOR_H),TRIM,.003)
        box(name+'T',(x,y,DOOR_H),(w+f,d,f),TRIM,.003)
    else:
        box(name+'L',(x,y-w/2,DOOR_H/2),(d,f,DOOR_H),TRIM,.003)
        box(name+'R',(x,y+w/2,DOOR_H/2),(d,f,DOOR_H),TRIM,.003)
        box(name+'T',(x,y,DOOR_H),(d,w+f,f),TRIM,.003)

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

floor_obj('LivingFloor',[(0,0),(3.12,0),(3.12,2.83),(4.113,2.83),(4.113,4.903),(0,4.903)],WOOD)
floor_obj('BedroomFloor',[(3.12,0),(6.265,0),(6.265,2.83),(3.12,2.83)],WOOD)
floor_obj('KitchenFloor',[(4.113,2.83),(6.265,2.83),(6.265,4.903),(4.113,4.903)],STONE)
floor_obj('BathroomFloor',[(1.143,4.903),(3.18,4.903),(3.18,6.523),(1.143,6.523)],STONE)
floor_obj('BalconyFloor',[(6.265,0),(7.327,0),(7.327,4.903),(6.265,4.903)],BAL)

main_boxes=[]; cut_boxes=[]
wallrun_boxes(main_boxes,0,0,6.265,0,[(.45,1.75,'window'),(3.65,5.55,'window')])
wallrun_boxes(main_boxes,0,0,0,4.903,[(3.76,4.62,'door')])
wallrun_boxes(main_boxes,7.327,0,7.327,4.903,[(.45,4.45,'window')])
wallrun_boxes(main_boxes,3.12,0,3.12,2.83,[(1.72,2.56,'door')])
wallrun_boxes(main_boxes,3.12,2.83,6.265,2.83,())
wallrun_boxes(main_boxes,4.113,2.83,4.113,4.903,[(.18,1.02,'door')])
wallrun_boxes(main_boxes,6.265,0,6.265,4.903,[(.30,2.48,'door'),(2.72,4.60,'door')])
wallrun_boxes(cut_boxes,0,4.903,1.143,4.903,())
wallrun_boxes(cut_boxes,1.143,4.903,3.18,4.903,[(.92,1.70,'door')])
wallrun_boxes(cut_boxes,3.18,4.903,7.327,4.903,())
wallrun_boxes(cut_boxes,1.143,4.903,1.143,6.523,())
wallrun_boxes(cut_boxes,1.143,6.523,3.18,6.523,())
wallrun_boxes(cut_boxes,3.18,4.903,3.18,6.523,())

fused_boxes_mesh('MAIN_WALLS', main_boxes, WALL)
cutwall=fused_boxes_mesh('CUTAWAY_WALLS', cut_boxes, WALL)

window('LivingWindow',1.10,0,1.30,'x')
window('BedroomWindow',4.60,0,1.70,'x')
box('BalconyGlass',(7.327,2.4515,1.42),(.025,4.68,2.60),GLASS,.002)
for yy in (.12,1.22,2.45,3.68,4.78): box('BalconyMullion',(7.327,yy,1.42),(.06,.045,2.68),FRAME,.002)
box('BalconyTop',(7.327,2.45,2.74),(.07,4.85,.07),FRAME,.002)
box('BalconyBottom',(7.327,2.45,.10),(.07,4.85,.07),FRAME,.002)
for yy in (.30,2.48,2.72,4.60): box('BalDoorPost',(6.265,yy,1.35),(.055,.055,2.65),FRAME,.002)
box('BalDoorGlass1',(6.265,1.39,1.34),(.02,2.05,2.55),GLASS,.002)
box('BalDoorGlass2',(6.265,3.66,1.34),(.02,1.72,2.55),GLASS,.002)
doorframe('EntryDoor',0,4.19,.86,'y')
doorframe('BedroomDoor',3.12,2.14,.84,'y')
doorframe('KitchenDoor',4.113,3.43,.84,'y')
doorframe('BathDoor',2.45,4.903,.78,'x')

box('TVConsole',(2.45,.27,.28),(1.20,.42,.50),CAB,.02)
box('TVScreen',(2.45,.06,1.12),(1.05,.035,.62),TV,.006)
box('LivingRug',(1.55,1.62,.018),(2.05,1.38,.028),RUG,.01)
box('KitchenBase',(5.20,4.58,.45),(1.90,.58,.88),CAB,.02)
box('KitchenCounter',(5.20,4.58,.92),(1.98,.64,.06),COUNTER,.01)
box('TallCabinet',(6.00,3.55,1.12),(.48,.62,2.18),CAB,.015)
box('SinkBasin',(4.68,4.56,.955),(.45,.36,.025),METAL,.01)
box('Cooktop',(5.68,4.56,.956),(.48,.36,.025),TV,.006)
box('Vanity',(1.55,5.45,.42),(.62,.48,.82),CAB,.02)
box('VanityTop',(1.55,5.45,.85),(.68,.54,.05),COUNTER,.01)
box('Mirror',(1.55,5.70,1.52),(.62,.025,.78),GLASS,.003)
box('ShowerGlass',(2.95,5.82,1.05),(.025,1.16,1.95),GLASS,.002)

assets=[
 ('sofa_02','Sofa',(0.70,1.58,0),(1.75,.86,.88),90),
 ('modern_coffee_table_01','CoffeeTable',(1.70,1.62,0),(1.05,.66,.48),0),
 ('modern_arm_chair_01','ArmChair',(2.38,1.00,0),(.82,.82,.95),-125),
 ('GothicBed_01','Bed',(4.82,1.30,0),(1.52,2.02,1.55),0),
 ('side_table_01','SideTable',(5.76,2.28,0),(.50,.45,.62),0),
 ('drawer_cabinet','BedroomCabinet',(3.63,.37,0),(1.10,.46,1.95),0),
 ('outdoor_table_chair_set_01','BalconySet',(6.78,3.60,0),(.86,1.35,.85),90),
 ('dining_chair_02','DiningChair',(2.45,2.25,0),(.56,.62,1.00),150),
 ('throw_pillows_01','Pillows',(4.86,1.10,.55),(.70,.34,.25),0),
 ('potted_plant_04','SmallPlant',(2.20,.62,0),(.34,.34,.42),0),
]
for a in assets:
    import_polyhaven(*a, CACHE)

world=bpy.context.scene.world or bpy.data.worlds.new('World')
bpy.context.scene.world=world
world.use_nodes=True
world.node_tree.nodes['Background'].inputs['Color'].default_value=(.040,.052,.064,1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value=.18

for name,loc,energy,size,color in [
 ('LivingArea',(1.65,2.0,2.62),300,2.0,(1,.84,.72)),
 ('BedroomArea',(4.80,1.35,2.62),220,1.55,(1,.84,.74)),
 ('KitchenArea',(5.20,3.85,2.56),230,1.2,(1,.92,.82)),
 ('BathArea',(2.1,5.65,2.48),135,.9,(1,.94,.88)),
]:
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color
    o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc
sd=bpy.data.lights.new('Sun','SUN');sd.energy=1.25;sd.angle=math.radians(6)
sun=bpy.data.objects.new('Sun',sd);bpy.context.collection.objects.link(sun);sun.rotation_euler=(math.radians(40),math.radians(-18),math.radians(-35))

camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);bpy.context.collection.objects.link(cam);bpy.context.scene.camera=cam
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=1280;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
try: scene.view_settings.look='AgX - Medium High Contrast'
except Exception: pass
scene.view_settings.exposure=-0.75

bpy.ops.wm.save_as_mainfile(filepath=str(DIST/'scene.blend'))
bpy.ops.export_scene.gltf(filepath=str(DIST/'scene.glb'),export_format='GLB',export_apply=True,export_lights=True,export_cameras=False,export_materials='EXPORT',export_yup=True)
cutwall.hide_render=True
cam.location=(9.2,10.2,7.5);cam.data.lens=50;look_at(cam,(3.55,2.75,.95))
scene.render.filepath=str(DIST/'preview-cutaway.png');bpy.ops.render.render(write_still=True)
cam.location=(1.55,4.35,1.62);cam.data.lens=36;look_at(cam,(1.45,.80,1.15))
scene.render.filepath=str(DIST/'preview-living.png');bpy.ops.render.render(write_still=True)
cutwall.hide_render=False
print('DONE', DIST)
