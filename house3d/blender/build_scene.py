import bpy, math, pathlib, sys
from mathutils import Vector
ROOT=pathlib.Path(__file__).resolve().parents[1];DIST=ROOT/'dist';CACHE=ROOT/'.asset_cache';DIST.mkdir(parents=True,exist_ok=True);CACHE.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(pathlib.Path(__file__).parent));from ph_assets import polyhaven_texture,import_polyhaven
W,H,T=7.327,4.903,.12;HEIGHT=2.80;DOOR_H=2.10;WIN_SILL=.82;WIN_HEAD=2.22
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def mat(name,color,rough=.55,metal=0):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough;b.inputs['Metallic'].default_value=metal;return m

def painted_wall(name='Warm Ivory Wall'):
 m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;nt.nodes.clear();out=nt.nodes.new('ShaderNodeOutputMaterial');bs=nt.nodes.new('ShaderNodeBsdfPrincipled');bs.inputs['Base Color'].default_value=(.79,.75,.66,1);bs.inputs['Roughness'].default_value=.82;noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=28;noise.inputs['Detail'].default_value=2.5;noise.inputs['Roughness'].default_value=.55;bump=nt.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.09;bump.inputs['Distance'].default_value=.025;nt.links.new(noise.outputs['Fac'],bump.inputs['Height']);nt.links.new(bump.outputs['Normal'],bs.inputs['Normal']);nt.links.new(bs.outputs['BSDF'],out.inputs['Surface']);return m

def add_uv(mesh,tile=1.0):
 uv=mesh.uv_layers.new(name='UVMap')
 for li,loop in enumerate(mesh.loops):
  v=mesh.vertices[loop.vertex_index].co;uv.data[li].uv=(v.x/tile,v.y/tile)

def floor(name,pts,material,z=.01):
 mesh=bpy.data.meshes.new(name+'Mesh');mesh.from_pydata([(x,y,z) for x,y in pts],[],[list(range(len(pts)))]);mesh.update();add_uv(mesh,1.2);o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(material);return o

def box(name,loc,size,material,bevel=.01,collection=None):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if material:o.data.materials.append(material)
 if bevel:mod=o.modifiers.new('soft_edges','BEVEL');mod.width=bevel;mod.segments=2
 if collection:
  for c in list(o.users_collection):c.objects.unlink(o)
  collection.objects.link(o)
 return o

def wallseg(name,x1,y1,x2,y2,z0=0,z1=HEIGHT,material=None,collection=None):
 dx=x2-x1;dy=y2-y1;L=(dx*dx+dy*dy)**.5+.035;ang=math.atan2(dy,dx);o=box(name,((x1+x2)/2,(y1+y2)/2,(z0+z1)/2),(L,T,z1-z0),material,0,collection);o.rotation_euler[2]=ang;return o

def wallrun(name,x1,y1,x2,y2,opens=(),material=None,collection=None):
 vert=abs(x2-x1)<1e-6;L=abs((y2-y1) if vert else (x2-x1));start=min(y1,y2) if vert else min(x1,x2);const=x1 if vert else y1;cur=0
 def seg(a,b,z0=0,z1=HEIGHT):
  if b-a<.005:return
  wallseg(name,const,start+a,const,start+b,z0,z1,material,collection) if vert else wallseg(name,start+a,const,start+b,const,z0,z1,material,collection)
 for a,b,k in sorted(opens):
  seg(cur,a)
  if k=='window':seg(a,b,0,WIN_SILL);seg(a,b,WIN_HEAD,HEIGHT)
  else:seg(a,b,DOOR_H,HEIGHT)
  cur=b
 seg(cur,L)

def window(name,x,y,w,axis='x'):
 f=.045;d=.055;h=WIN_HEAD-WIN_SILL
 if axis=='x':
  box(name+'Glass',(x,y,(WIN_SILL+WIN_HEAD)/2),(w-.08,.018,h-.08),GLASS,.002);box(name+'L',(x-w/2+f/2,y,1.52),(f,d,h),FRAME,.003);box(name+'R',(x+w/2-f/2,y,1.52),(f,d,h),FRAME,.003);box(name+'T',(x,y,WIN_HEAD-f/2),(w,d,f),FRAME,.003);box(name+'B',(x,y,WIN_SILL+f/2),(w,d,f),FRAME,.003)
 else:
  box(name+'Glass',(x,y,(WIN_SILL+WIN_HEAD)/2),(.018,w-.08,h-.08),GLASS,.002);box(name+'L',(x,y-w/2+f/2,1.52),(d,f,h),FRAME,.003);box(name+'R',(x,y+w/2-f/2,1.52),(d,f,h),FRAME,.003);box(name+'T',(x,y,WIN_HEAD-f/2),(d,w,f),FRAME,.003);box(name+'B',(x,y,WIN_SILL+f/2),(d,w,f),FRAME,.003)

def doorframe(name,x,y,w,axis='x'):
 f=.05;d=.09
 if axis=='x':box(name+'L',(x-w/2,y,DOOR_H/2),(f,d,DOOR_H),TRIM,.004);box(name+'R',(x+w/2,y,DOOR_H/2),(f,d,DOOR_H),TRIM,.004);box(name+'T',(x,y,DOOR_H),(w+f,d,f),TRIM,.004)
 else:box(name+'L',(x,y-w/2,DOOR_H/2),(d,f,DOOR_H),TRIM,.004);box(name+'R',(x,y+w/2,DOOR_H/2),(d,f,DOOR_H),TRIM,.004);box(name+'T',(x,y,DOOR_H),(d,w+f,f),TRIM,.004)

def look_at(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

WALL=painted_wall();WOOD=polyhaven_texture('wooden_floor_02','Warm Oak Floor',CACHE,.72);BATH=polyhaven_texture('marble_tiles','Warm Stone Tile',CACHE,1.35)
FRAME=mat('Window Frame',(.055,.065,.075),.25,.68);TRIM=mat('Warm White Trim',(.82,.79,.72),.40);COUNTER=mat('Countertop',(.30,.28,.25),.25);CAB=mat('Cabinet Oak',(.45,.27,.13),.38);BAL=mat('Balcony Stone',(.36,.36,.34),.72);RUG=mat('Low Saturation Rug',(.46,.42,.36),.92);TV=mat('TV Black',(.012,.016,.020),.18);METAL=mat('Brushed Metal',(.34,.36,.38),.28,.72)
GLASS=bpy.data.materials.new('Architectural Glass');GLASS.use_nodes=True;b=GLASS.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(.68,.82,.92,1);b.inputs['Roughness'].default_value=.06;(b.inputs.get('Transmission Weight') or b.inputs.get('Transmission')).default_value=.88;b.inputs['IOR'].default_value=1.45

floor('LivingFloor',[(0,0),(3.12,0),(3.12,2.83),(4.113,2.83),(4.113,4.903),(0,4.903)],WOOD);floor('BedroomFloor',[(3.12,0),(6.265,0),(6.265,2.83),(3.12,2.83)],WOOD);floor('KitchenFloor',[(4.113,2.83),(6.265,2.83),(6.265,4.903),(4.113,4.903)],BATH);floor('BathroomFloor',[(1.143,4.903),(3.18,4.903),(3.18,6.523),(1.143,6.523)],BATH);floor('BalconyFloor',[(6.265,0),(7.327,0),(7.327,4.903),(6.265,4.903)],BAL)
cut=bpy.data.collections.new('CutawayCollection');bpy.context.scene.collection.children.link(cut)
wallrun('OuterNorth',0,0,6.265,0,[(.45,1.75,'window'),(3.65,5.55,'window')],WALL);wallrun('OuterWest',0,0,0,4.903,[(3.76,4.62,'door')],WALL);wallrun('OuterSouthA',0,4.903,1.143,4.903,(),WALL,cut);wallrun('BathroomTop',1.143,4.903,3.18,4.903,[(.92,1.70,'door')],WALL,cut);wallrun('OuterSouthB',3.18,4.903,7.327,4.903,(),WALL,cut);wallrun('BathWest',1.143,4.903,1.143,6.523,(),WALL,cut);wallrun('BathSouth',1.143,6.523,3.18,6.523,(),WALL,cut);wallrun('BathEast',3.18,4.903,3.18,6.523,(),WALL,cut);wallrun('BedWest',3.12,0,3.12,2.83,[(1.72,2.56,'door')],WALL);wallrun('BedSouth',3.12,2.83,6.265,2.83,(),WALL);wallrun('KitchenWest',4.113,2.83,4.113,4.903,[(.18,1.02,'door')],WALL);wallrun('BalconyDivider',6.265,0,6.265,4.903,[(.30,2.48,'door'),(2.72,4.60,'door')],WALL)
box('BalconyGlass',(7.327,2.4515,1.42),(.025,4.68,2.60),GLASS,.002)
for yy in (.12,1.22,2.45,3.68,4.78):box('BalconyMullion',(7.327,yy,1.42),(.07,.045,2.68),FRAME,.002)
box('BalconyTop',(7.327,2.45,2.74),(.07,4.85,.08),FRAME,.002);box('BalconyBottom',(7.327,2.45,.10),(.07,4.85,.08),FRAME,.002);window('LivingWindow',1.10,0,1.30);window('BedroomWindow',4.60,0,1.70);doorframe('EntryDoor',0,4.19,.86,'y');doorframe('BedroomDoor',3.12,2.14,.84,'y');doorframe('KitchenDoor',4.113,3.43,.84,'y');doorframe('BathDoor',2.45,4.903,.78)
for yy in (.30,2.48,2.72,4.60):box('BalDoorPost',(6.265,yy,1.35),(.06,.055,2.65),FRAME,.002)
box('BalDoorGlass1',(6.265,1.39,1.34),(.02,2.05,2.55),GLASS,.002);box('BalDoorGlass2',(6.265,3.66,1.34),(.02,1.72,2.55),GLASS,.002)
# Built-ins and architectural details
box('LivingRug',(1.55,1.62,.018),(2.05,1.38,.028),RUG,.012);box('TVConsole',(2.45,.26,.28),(1.22,.42,.50),CAB,.024);box('TVScreen',(2.45,.055,1.12),(1.05,.035,.62),TV,.010)
box('KitchenBase',(5.20,4.58,.45),(1.90,.58,.88),CAB,.025);box('KitchenCounter',(5.20,4.58,.92),(1.98,.64,.06),COUNTER,.018);box('TallCabinet',(6.00,3.55,1.12),(.48,.62,2.18),CAB,.02);box('SinkBasin',(4.68,4.56,.955),(.45,.36,.025),METAL,.02);box('Cooktop',(5.68,4.56,.956),(.48,.36,.025),TV,.008);box('Backsplash',(5.20,4.87,1.38),(2.05,.025,.74),BATH,.005)
box('Vanity',(1.55,5.45,.42),(.62,.48,.82),CAB,.025);box('VanityTop',(1.55,5.45,.85),(.68,.54,.05),COUNTER,.015);box('Mirror',(1.55,5.70,1.52),(.62,.025,.78),GLASS,.005);box('ShowerGlass',(2.95,5.82,1.05),(.025,1.16,1.95),GLASS,.003)
assets=[('sofa_02','Sofa',(0.70,1.58,0),(1.75,.86,.88),90),('modern_coffee_table_01','CoffeeTable',(1.70,1.62,0),(1.05,.66,.48),0),('modern_arm_chair_01','ArmChair',(2.38,1.00,0),(.82,.82,.95),-125),('GothicBed_01','Bed',(4.82,1.30,0),(1.52,2.02,1.55),0),('side_table_01','SideTable',(5.76,2.28,0),(.50,.45,.62),0),('drawer_cabinet','BedroomCabinet',(3.63,.37,0),(1.10,.46,1.95),0),('outdoor_table_chair_set_01','BalconySet',(6.78,3.60,0),(.86,1.35,.85),90),('dining_chair_02','DiningChair',(2.45,2.25,0),(.56,.62,1.00),150),('throw_pillows_01','Pillows',(4.86,1.10,.55),(.70,.34,.25),0),('potted_plant_04','SmallPlant',(2.20,.62,0),(.34,.34,.42),0)]
for a in assets:import_polyhaven(*a,CACHE)
cut_root=bpy.data.objects.new('CUTAWAY_WALLS',None);bpy.context.collection.objects.link(cut_root)
for o in list(cut.objects):o.parent=cut_root
world=bpy.context.scene.world or bpy.data.worlds.new('World');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(.055,.070,.085,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for name,loc,energy,size,color in [('LivingArea',(1.7,2.1,2.64),520,2.1,(1,.84,.70)),('BedroomArea',(4.8,1.3,2.64),360,1.6,(1,.84,.72)),('KitchenArea',(5.2,3.85,2.56),360,1.3,(1,.91,.80)),('BathArea',(2.1,5.65,2.45),210,.9,(1,.92,.84))]:
 d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.shape='DISK';d.size=size;d.color=color;o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);o.location=loc
sd=bpy.data.lights.new('Sun','SUN');sd.energy=2.1;sd.angle=math.radians(6);sun=bpy.data.objects.new('Sun',sd);bpy.context.collection.objects.link(sun);sun.rotation_euler=(math.radians(38),math.radians(-18),math.radians(-35))
camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);bpy.context.collection.objects.link(cam);bpy.context.scene.camera=cam;cam.data.lens=47
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1280;scene.render.resolution_y=900;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
try:scene.view_settings.look='AgX - Medium High Contrast'
except Exception:pass
# Export full interactive model first.
bpy.ops.wm.save_as_mainfile(filepath=str(DIST/'scene.blend'));bpy.ops.export_scene.gltf(filepath=str(DIST/'scene.glb'),export_format='GLB',export_apply=True,export_lights=True,export_cameras=False,export_materials='EXPORT',export_yup=True)
# Render QA views. Hide the south/cutaway shell only for cutaway/interior renders.
cam.location=(9,-10,8);look_at(cam,(3.6,2.5,1.0));cut_root.hide_render=False;scene.render.filepath=str(DIST/'preview-exterior.png');bpy.ops.render.render(write_still=True)
cut_root.hide_render=True;cam.location=(9,10.5,7.2);look_at(cam,(3.55,2.75,.85));scene.render.filepath=str(DIST/'preview-cutaway.png');bpy.ops.render.render(write_still=True)
cam.location=(1.40,3.90,1.55);cam.data.lens=35;look_at(cam,(1.45,.80,1.10));scene.render.filepath=str(DIST/'preview-living.png');bpy.ops.render.render(write_still=True);cut_root.hide_render=False
print('DONE',DIST)
