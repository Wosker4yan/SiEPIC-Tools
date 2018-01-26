
#################################################################################
#                SiEPIC Tools - scripts                                         #
#################################################################################
'''

path_to_waveguide
roundpath_to_waveguide
waveguide_to_path
waveguide_length
waveguide_length_diff
waveguide_heal
auto_route
snap_component
delete_top_cells
compute_area
calibreDRC
auto_coord_extract
calculate_area
trim_netlist
layout_check
open_PDF_files
open_folder
user_select_opt_in
fetch_measurement_data_from_github
measurement_vs_simulation

'''


import pya

def path_to_waveguide(params = None, cell = None, lv_commit=True):
  from . import _globals
  from .utils import select_paths
  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()
  
  if lv_commit:
    lv.transaction("Path to Waveguide")

  if params is None: params = _globals.WG_GUI.get_parameters()
  if params is None: return
  selected_paths = select_paths(TECHNOLOGY['Waveguide'], cell)
  selection = []

  warning = pya.QMessageBox()
  warning.setStandardButtons(pya.QMessageBox.Yes | pya.QMessageBox.Cancel)
  warning.setDefaultButton(pya.QMessageBox.Yes)
  for obj in selected_paths:
    path = obj.shape.path
    path.unique_points()
    if not path.is_manhattan():
      warning.setText("Warning: Waveguide segments (first, last) are not Manhattan (vertical, horizontal).")
      warning.setInformativeText("Do you want to Proceed?")
      if(pya.QMessageBox_StandardButton(warning.exec_()) == pya.QMessageBox.Cancel):
        return
    if not path.radius_check(params['radius']/TECHNOLOGY['dbu']):
      warning.setText("Warning: One of the waveguide segments has insufficient length to accommodate the desired bend radius.")
      warning.setInformativeText("Do you want to Proceed?")
      if(pya.QMessageBox_StandardButton(warning.exec_()) == pya.QMessageBox.Cancel):
        return

    path.snap(cell.find_pins())
    
    # 0.25: path.to_dtype
#    path = pya.DPath(path.get_dpoints(), path.width) * TECHNOLOGY['dbu']
#    path.width = path.width * TECHNOLOGY['dbu']
    Dpath = path.to_dtype(TECHNOLOGY['dbu'])
    width_devrec = max([wg['width'] for wg in params['wgs']]) + _globals.WG_DEVREC_SPACE * 2
    try:
      pcell = ly.create_cell("Waveguide", TECHNOLOGY['technology_name'], { "path": Dpath,
                                                                     "radius": params['radius'],
                                                                     "width": params['width'],
                                                                     "adiab": params['adiabatic'],
                                                                     "bezier": params['bezier'],
                                                                     "layers": [wg['layer'] for wg in params['wgs']] + ['DevRec'],
                                                                     "widths": [wg['width'] for wg in params['wgs']] + [width_devrec],
                                                                     "offsets": [wg['offset'] for wg in params['wgs']] + [0]} )
      print ("SiEPIC.scripts.path_to_waveguide(): Waveguide from %s, %s" % (TECHNOLOGY['technology_name'],pcell))
    except:
      pass
    if not pcell:
      try:
        pcell = ly.create_cell("Waveguide", "SiEPIC General", { "path": Dpath,
                                                                     "radius": params['radius'],
                                                                     "width": params['width'],
                                                                     "adiab": params['adiabatic'],
                                                                     "bezier": params['bezier'],
                                                                     "layers": [wg['layer'] for wg in params['wgs']] + ['DevRec'],
                                                                     "widths": [wg['width'] for wg in params['wgs']] + [width_devrec],
                                                                     "offsets": [wg['offset'] for wg in params['wgs']] + [0]} )
        print ("SiEPIC.scripts.path_to_waveguide(): Waveguide from SiEPIC General, %s" % pcell)
      except:
        pass
    if not pcell:
      raise Exception("'Waveguide' in 'SiEPIC General' library is not available. Check that the library was loaded successfully.")
    selection.append(pya.ObjectInstPath())
    selection[-1].top = obj.top
    selection[-1].append_path(pya.InstElement.new(cell.insert(pya.CellInstArray(pcell.cell_index(), pya.Trans(pya.Trans.R0, 0, 0)))))

    obj.shape.delete()

  lv.clear_object_selection()
  lv.object_selection = selection
  if lv_commit:
    lv.commit()

'''
convert a KLayout ROUND_PATH, which was used to make a waveguide 
in SiEPIC_EBeam_PDK versions up to v0.1.41, back to a Path.
This allows the user to migrate designs to the new Waveguide PCell.
'''
def roundpath_to_waveguide(verbose=False):

  from . import _globals
  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()
  dbu = TECHNOLOGY['dbu']
  
  # Record a transaction, to enable "undo"
  lv.transaction("ROUND_PATH to Waveguide")
  
  if verbose:
    print("SiEPIC.scripts.roundpath_to_waveguide()")
  
  # record objects to delete:
  to_delete = []
  # new objects will become selected after the waveguide-to-path operation
  new_selection = []  
  # Find the selected objects
  object_selection = lv.object_selection   # returns ObjectInstPath[].

  Waveguide_Types = ["ROUND_PATH"]
  
  if object_selection == []:
    if verbose:
      print("Nothing selected.  Automatically selecting waveguides.")
    # find all instances, specifically, Waveguides:
    for inst in cell.each_inst():
      if verbose:
        print("Cell: %s" % (inst.cell.basic_name() ) )
      if inst.cell.basic_name() in Waveguide_Types:
        n = len(object_selection)
        object_selection.append( pya.ObjectInstPath() )
        object_selection[n].top = cell.cell_index()
        object_selection[n].append_path(pya.InstElement.new(inst))
    # Select the newly added objects
    lv.object_selection = object_selection
  
  is_ROUNDPATH = False
  for o in object_selection:
    # Find the selected waveguides
    if o.is_cell_inst():
      if verbose:
        print("Selected object is a cell.")
      oinst = o.inst()
      if oinst.is_pcell():
        c = oinst.cell
        if c.basic_name() in Waveguide_Types: # and c.pcell_parameters_by_name()['layer'] == LayerSi:
          LayerSiN = c.pcell_parameters_by_name()['layer'] 
          radius = c.pcell_parameters_by_name()['radius'] 
          if verbose:
            print("%s on Layer %s." % (c.basic_name(), LayerSiN) )
          is_ROUNDPATH = True
          trans = oinst.trans
  
    elif o.shape:
      if verbose:
        print("Selected object is a shape.")
      c = o.shape.cell
      if c.basic_name() in Waveguide_Types and c.is_pcell_variant(): # and c.pcell_parameters_by_name()['layer'] == LayerSi:
        # we have a waveguide GUIDING_LAYER selected
        LayerSiN = c.pcell_parameters_by_name()['layer'] 
        radius = c.pcell_parameters_by_name()['radius'] 
        if verbose:
          print("Selected object is a GUIDING_LAYER in %s on Layer %s." % (c.basic_name(),LayerSiN) )
        trans = o.source_trans().s_trans()
        o_instpathlen = o.path_length()
        oinst = o.path_nth(o_instpathlen-1).inst()
        is_ROUNDPATH = True
  
    # We now have a waveguide ROUND_PATH PCell, with variables: o (ObjectInstPath), oinst (Instance), c (Cell)
    if is_ROUNDPATH == True:
      path_obj = c.pcell_parameters_by_name()['path']
      if verbose:
        print( path_obj ) 
      wg_width = path_obj.width/dbu
      # convert wg_path (in microns) to database numbers
  
      from ._globals import KLAYOUT_VERSION
      if KLAYOUT_VERSION > 24:
        new_wg = cell.shapes(ly.layer(LayerSiN)).insert(path_obj.transformed(trans))
      else:
        v = pya.MessageBox.warning("KLayout 0.25 or higher required.", "ROUND_PATH to Waveguide is implemented using KLayout 0.25 or higher functionality.", pya.MessageBox.Ok)
  
      # Leave the newly created path selected, to make it obvious to the user.
      # http://klayout.de/forum/comments.php?DiscussionID=747
      new_selection.append( pya.ObjectInstPath() )
      new_selection[-1].layer = ly.layer(LayerSiN)
      new_selection[-1].shape = new_wg
      new_selection[-1].top = o.top
      new_selection[-1].cv_index = o.cv_index
      
      # Convert the path to a Waveguide:
      from SiEPIC import scripts
      scripts.path_to_waveguide(lv_commit=False)

      to_delete.append(oinst) # delete the instance; leaves behind the cell if it's not used
          
  for t in to_delete:
    t.delete()
  
  # Clear the layout view selection, since we deleted some objects (but others may still be selected):
  lv.clear_object_selection()
  # Select the newly added objects
  lv.object_selection = new_selection       
  # Record a transaction, to enable "undo"
  lv.commit()
    
  if not(is_ROUNDPATH):
    v = pya.MessageBox.warning("No ROUND_PATH selected", "No ROUND_PATH selected.\nPlease select a ROUND_PATH. \nIt will get converted to a path.", pya.MessageBox.Ok)


def waveguide_to_path(cell = None):
  from SiEPIC import _globals
  from SiEPIC.utils import select_waveguides, get_technology
  TECHNOLOGY = get_technology()
  
  lv = pya.Application.instance().main_window().current_view()
  if lv == None:
    raise Exception("No view selected")
  
  if cell is None:
    ly = lv.active_cellview().layout()
    if ly == None:
      raise Exception("No active layout")
    cell = lv.active_cellview().cell
    if cell == None:
      raise Exception("No active cell")
  else:
    ly = cell.layout()
    
  lv.transaction("waveguide to path")

  # record objects to delete:
  to_delete = []
  
  waveguides = select_waveguides(cell)
  selection = []
  for obj in waveguides:
    # path from waveguide guiding shape
    waveguide = obj.inst()

    if 0:
      # Python 2 & 3 fix:
      from SiEPIC.utils import advance_iterator
      itr = waveguide.cell.shapes(waveguide.layout().guiding_shape_layer()).each()
      path1 = advance_iterator(itr)

    from ._globals import KLAYOUT_VERSION
    
    if KLAYOUT_VERSION > 24:
      path = waveguide.cell.pcell_parameters_by_name()['path']
    else:
      # waveguide path and width from Waveguide PCell
      path1 = waveguide.cell.pcell_parameters_by_name()['path']
      path = pya.Path()
      path.width = waveguide.cell.pcell_parameters_by_name()['width']/TECHNOLOGY['dbu']
      pts=[]
      for pt in [pt1 for pt1 in (path1).each_point()]:
        if type(pt) == pya.Point:
          # for instantiated PCell
          pts.append (pya.Point())
        else:
          # for waveguide from path
          pts.append (pya.Point().from_dpoint(pt*(1/TECHNOLOGY['dbu'])))
      path.points = pts

    selection.append(pya.ObjectInstPath())
    selection[-1].layer = ly.layer(TECHNOLOGY['Waveguide'])
    # DPath.transformed requires DTrans. waveguide.trans is a Trans object
    selection[-1].shape = cell.shapes(ly.layer(TECHNOLOGY['Waveguide'])).insert(path.transformed(waveguide.trans))
    selection[-1].top = obj.top
    selection[-1].cv_index = obj.cv_index
    
    if 1:
      # deleting the instance was ok, but would leave the cell which ends up as an uninstantiated top cell
      # obj.inst().delete()
      to_delete.append(obj.inst())
    else:
      # delete the cell (KLayout also removes the PCell)
      # deleting it removes the cell entirely (which may be used elsewhere ?)
      # intermittent crashing...
      to_delete.append(waveguide.cell) 


  # deleting instance or cell should be done outside of the for loop, otherwise each deletion changes the instance pointers in KLayout's internal structure
  [t.delete() for t in to_delete]

  # Clear the layout view selection, since we deleted some objects (but others may still be selected):
  lv.clear_object_selection()
  # Select the newly added objects
  lv.object_selection = selection
  # Record a transaction, to enable "undo"
  lv.commit()


def waveguide_length():

  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()
  import SiEPIC.utils
    
  selection = lv.object_selection
  if len(selection) == 1 and selection[0].inst().is_pcell() and "Waveguide" in selection[0].inst().cell.basic_name():
    cell = selection[0].inst().cell
    area = SiEPIC.utils.advance_iterator(cell.each_shape(cell.layout().layer(TECHNOLOGY['Waveguide']))).polygon.area()
    width = cell.pcell_parameters_by_name()['width']/cell.layout().dbu
    pya.MessageBox.warning("Waveguide Length", "Waveguide length (um): %s" % str(area/width*cell.layout().dbu), pya.MessageBox.Ok)
  else:
    pya.MessageBox.warning("Selection is not a waveguide", "Select one waveguide you wish to measure.", pya.MessageBox.Ok)
  
def waveguide_length_diff():

  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()
  import SiEPIC.utils
    
  selection = lv.object_selection
  if len(selection) == 2 and selection[0].inst().is_pcell() and "Waveguide" in selection[0].inst().cell.basic_name() and selection[1].inst().is_pcell() and "Waveguide" in selection[1].inst().cell.basic_name():
    cell = selection[0].inst().cell
    area1 = SiEPIC.utils.advance_iterator(cell.each_shape(cell.layout().layer(TECHNOLOGY['Waveguide']))).polygon.area()
    width1 = cell.pcell_parameters_by_name()['width']/cell.layout().dbu
    cell = selection[1].inst().cell
    area2 = SiEPIC.utils.advance_iterator(cell.each_shape(cell.layout().layer(TECHNOLOGY['Waveguide']))).polygon.area()
    width2 = cell.pcell_parameters_by_name()['width']/cell.layout().dbu
    pya.MessageBox.warning("Waveguide Length Difference", "Difference in waveguide lengths (um): %s" % str(abs(area1/width1 - area2/width2)*cell.layout().dbu), pya.MessageBox.Ok)
  else:
    pya.MessageBox.warning("Selection are not a waveguides", "Select two waveguides you wish to measure.", pya.MessageBox.Ok)

def waveguide_heal():
  print("waveguide_heal")

def auto_route():
  print("auto_route")
  

'''
SiEPIC-Tools: Snap Component

by Lukas Chrostowski (c) 2016-2017

This Python function implements snapping of one component to another. 

Usage:
- Click to select the component you wish to move (selected)
- Hover the mouse over the component you wish to align to (transient)
- Shift-O to run this script
- The function will find the closest pins between these components, and move the selected component

Version history:

Lukas Chrostowski           2016/03/08
 - Initial version
 
Lukas Chrostowski           2017/12/16
 - Updating to SiEPIC-Tools 0.3.x module based approach rather than a macro
   and without optical components database
 - Strict assumption that pin directions in the component are consistent, namely
   they indicate which way the signal is LEAVING the component 
   (path starts with the point inside the DevRec, then the point outside)
   added to wiki https://github.com/lukasc-ubc/SiEPIC_EBeam_PDK/wiki/Component-and-PCell-Layout
   This avoids the issue of components ending up on top of each other incorrectly.
   Ensures that connections are valid

Lukas Chrostowski           2017/12/17
 - removing redundant code, and replacing with Brett's functions:
   - Cell.find_pins, rather than code within.
   
'''

def snap_component():
  print("*** snap_component, move selected object to snap onto the transient: ")
  
  from . import _globals

  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()

  # Define layers based on PDK:
  LayerSiN = TECHNOLOGY['Waveguide']
  LayerPinRecN = TECHNOLOGY['PinRec']
  LayerDevRecN = TECHNOLOGY['DevRec']
  LayerFbrTgtN = TECHNOLOGY['FbrTgt']
  LayerErrorN = TECHNOLOGY['Errors']
  
  # we need two objects.  One is selected, and the other is a transient selection
  if lv.has_transient_object_selection() == False:
    print("No transient selection")
    v = pya.MessageBox.warning("No transient selection", "Hover the mouse (transient selection) over the object to which you wish to snap to.\nEnsure transient selection is enabled in Settings - Applications - Selection.", pya.MessageBox.Ok)
  else:
    # find the transient selection:
    o_transient_iter = lv.each_object_selected_transient()
    o_transient = next(o_transient_iter)  # returns ObjectInstPath[].

    # Find the selected objects
    o_selection = lv.object_selection   # returns ObjectInstPath[].

    if len(o_selection) < 1:
      v = pya.MessageBox.warning("No selection", "Select the object you wish to be moved.", pya.MessageBox.Ok)
    if len(o_selection) > 1:
      v = pya.MessageBox.warning("Too many selected", "Select only one object you wish to be moved.", pya.MessageBox.Ok)
    else:
      o_selection = o_selection[0]
      if o_selection.is_cell_inst()==False:
        v = pya.MessageBox.warning("No selection", "The selected object must be an instance (not primitive polygons)", pya.MessageBox.Ok)
      elif o_transient.is_cell_inst()==False:
        v = pya.MessageBox.warning("No selection", "The selected object must be an instance (not primitive polygons)", pya.MessageBox.Ok)
      elif o_selection.inst().is_regular_array():
        v = pya.MessageBox.warning("Array", "Selection was an array. \nThe array was 'exploded' (Edit | Selection | Resolve Array). \nPlease select the objects and try again.", pya.MessageBox.Ok)
        # Record a transaction, to enable "undo"
        lv.transaction("Object snapping - exploding array")
        o_selection.inst().explode()
        # Record a transaction, to enable "undo"
        lv.commit()
      elif o_transient.inst().is_regular_array():
        v = pya.MessageBox.warning("Array", "Selection was an array. \nThe array was 'exploded' (Edit | Selection | Resolve Array). \nPlease select the objects and try again.", pya.MessageBox.Ok)
        # Record a transaction, to enable "undo"
        lv.transaction("Object snapping - exploding array")
        o_transient.inst().explode()
        # Record a transaction, to enable "undo"
        lv.commit()      
      elif o_transient == o_selection:
        v = pya.MessageBox.warning("Same selection", "We need two different objects: one selected, and one transient (hover mouse over).", pya.MessageBox.Ok)
      else: 
        # we have two instances, we can snap them together:

        # Find the pins within the two cell instances:     
        pins_transient = o_transient.inst().find_pins()
        pins_selection = o_selection.inst().find_pins()
        print("all pins_transient (x,y): %s" % [[point.x, point.y] for point in [pin.center for pin in pins_transient]] )
        print("all pins_selection (x,y): %s" % [[point.x, point.y] for point in [pin.center for pin in pins_selection]] )

        # create a list of all pin pairs for comparison;
        # pin pairs must have a 180 deg orientation (so they can be connected);
        # then sort to find closest ones
        # nested list comprehension, tutorial: https://spapas.github.io/2016/04/27/python-nested-list-comprehensions/
        pin_pairs = sorted( [ [pin_t, pin_s] 
          for pin_t in pins_transient \
          for pin_s in pins_selection \
          if ((pin_t.rotation - pin_s.rotation)%360) == 180 and pin_t.type == _globals.PIN_TYPES.OPTICAL and pin_s.type == _globals.PIN_TYPES.OPTICAL ],
          key=lambda x: x[0].center.distance(x[1].center) )

        if pin_pairs:
          print("shortest pins_transient & pins_selection (x,y): %s" % [[point.x, point.y] for point in [pin.center for pin in pin_pairs[0]]] )
          print("shortest distance: %s" % pin_pairs[0][0].center.distance(pin_pairs[0][1].center) )

          trans = pya.Trans(pya.Trans.R0, pin_pairs[0][0].center - pin_pairs[0][1].center)
          print("translation: %s" % trans )

          # Record a transaction, to enable "undo"
          lv.transaction("Object snapping")
          # Move the selected object
          o_selection.inst().transform(trans)
          # Record a transaction, to enable "undo"
          lv.commit()
        else:
          v = pya.MessageBox.warning("Snapping failed", 
            "Snapping failed. \nNo matching pins found. \nNote that pins must have exactly matching orientations (180 degrees)", pya.MessageBox.Ok)

        pya.Application.instance().main_window().message('SiEPIC snap_components: moved by %s.' %trans, 2000)

        return
# end def snap_component()
  

# keep the selected top cell; delete everything else
def delete_top_cells():

  def delete_cells(ly, cell):
    if cell in ly.top_cells():
      ly.delete_cells([tcell for tcell in ly.each_top_cell() if tcell != cell.cell_index()])
    if len(ly.top_cells()) > 1:
      delete_cells(ly, cell)

  from .utils import get_layout_variables
  TECHNOLOGY, lv, ly, cell = get_layout_variables()
    
  if cell in ly.top_cells():
    lv.transaction("Delete extra top cells")
    delete_cells(ly, cell)
    lv.commit()
  else:
    v = pya.MessageBox.warning("No top cell selected", "No top cell selected.\nPlease select a top cell to keep\n(not a sub-cell).", pya.MessageBox.Ok)
  
  
def compute_area():
  print("compute_area")
  
def calibreDRC(params = None, cell = None, GUI = False):
  from . import _globals
  import sys, os, pipes, codecs

  lv = pya.Application.instance().main_window().current_view()
  if lv == None:
    raise Exception("No view selected")

  if cell is None:
    ly = lv.active_cellview().layout() 
    if ly == None:
      raise Exception("No active layout")
    cell = lv.active_cellview().cell
    if cell == None:
      raise Exception("No active cell")
  else:
    ly = cell.layout()
  
  status = _globals.DRC_GUI.return_status()
  if GUI:
    if status is None and params is None:
      #Load defaults from CALIBRE.xml:
      from .utils import load_Calibre
      CALIBRE = load_Calibre()
      if CALIBRE:
        _globals.DRC_GUI.window.findChild('pdk').text = CALIBRE['Calibre']['remote_pdk_location']
        _globals.DRC_GUI.window.findChild('calibre').text = CALIBRE['Calibre']['remote_calibre_script']
        print('loaded CALIBRE.xml')
      _globals.DRC_GUI.show()
  else:
    if not params:
      from .utils import load_Calibre
      CALIBRE = load_Calibre()
      params={}
      params['pdk'] = CALIBRE['Calibre']['remote_pdk_location']
      params['calibre'] = CALIBRE['Calibre']['remote_calibre_script']
      params['remote_calibre_rule_deck_main_file'] = CALIBRE['Calibre']['remote_calibre_rule_deck_main_file']
      params['remote_additional_commands'] = CALIBRE['Calibre']['remote_additional_commands']

  if not GUI or not (status is None and params is None):
    if status is False: return
    if params is None: params = _globals.DRC_GUI.get_parameters()
    
    if any(value == '' for key, value in params.items()):
      raise Exception("Missing information")

    lv.transaction("calibre drc")
    
    import time
    progress = pya.RelativeProgress("Calibre DRC", 5)
    progress.format = "Saving Layout to Temporary File"
    progress.set(1, True)
    time.sleep(1)
    pya.Application.instance().main_window().repaint()

    # Local temp folder:
    local_path = _globals.TEMP_FOLDER
    print("SiEPIC.scripts.calibreDRC; local tmp folder: %s" % local_path )
    local_file = os.path.basename(lv.active_cellview().filename())
    if not local_file:
      local_file = 'layout'
    local_pathfile = os.path.join(local_path, local_file)

    # Layout path and filename:
    mw = pya.Application.instance().main_window()
    layout_path = mw.current_view().active_cellview().filename()  # /path/file.gds
    layout_filename = os.path.basename(layout_path)               # file.gds
    layout_basefilename = layout_filename.split('.')[0]           # file   
     
    remote_path = "/tmp/${USER}_%s" % layout_basefilename
    
    results_file = layout_basefilename + ".rve"
    results_pathfile = os.path.join(os.path.dirname(local_pathfile), results_file)
    tmp_ly = ly.dup()
    [cell.flatten(True) for cell in tmp_ly.each_cell()]
    opts = pya.SaveLayoutOptions()
    opts.format = "GDS2"
    tmp_ly.write(local_pathfile, opts)
    
    with codecs.open(os.path.join(local_path, 'run_calibre'), 'w', encoding="utf-8") as file:
      cal_script  = '#!/bin/tcsh \n'
      cal_script += 'source %s \n' % params['calibre']
      cal_script += '%s \n' % params['remote_additional_commands']
      cal_script += '$MGC_HOME/bin/calibre -drc -hier -turbo -nowait drc.cal \n'
      file.write(cal_script)

    with codecs.open(os.path.join(local_path, 'drc.cal'), 'w', encoding="utf-8") as file:
      cal_deck  = 'LAYOUT PATH  "%s"\n' % os.path.basename(local_pathfile)
      cal_deck += 'LAYOUT PRIMARY "%s"\n' % cell.name
      cal_deck += 'LAYOUT SYSTEM GDSII\n'
      cal_deck += 'DRC RESULTS DATABASE "drc.rve" ASCII\n'
      cal_deck += 'DRC MAXIMUM RESULTS ALL\n'
      cal_deck += 'DRC MAXIMUM VERTEX 4096\n'
      cal_deck += 'DRC CELL NAME YES CELL SPACE XFORM\n'
      cal_deck += 'VIRTUAL CONNECT COLON NO\n'
      cal_deck += 'VIRTUAL CONNECT REPORT NO\n'
      cal_deck += 'DRC ICSTATION YES\n'
      cal_deck += 'INCLUDE "%s/%s"\n' % (params['pdk'], params['remote_calibre_rule_deck_main_file'])
      file.write(cal_deck)

    import platform
    version = platform.python_version()
    out = ''
    if version.find("2.") > -1:
      import commands
      cmd = commands.getstatusoutput

      progress.set(2, True)
      progress.format = "Uploading Layout and Scripts"
      pya.Application.instance().main_window().repaint()
      
      out += cmd('ssh drc "mkdir -p %s"' % (remote_path))[1]
      out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, local_file, remote_path))[1]
      out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, 'run_calibre', remote_path))[1]
      out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, 'drc.cal', remote_path))[1]

      progress.set(3, True)
      progress.format = "Checking Layout for Errors"
      pya.Application.instance().main_window().repaint()
    
      out += cmd('ssh drc "cd %s && source run_calibre"' % (remote_path))[1]

      progress.set(4, True)
      progress.format = "Downloading Results"
      pya.Application.instance().main_window().repaint()
      
      out += cmd('cd "%s" && scp drc:%s "%s"' % (local_path, remote_path + "/drc.rve", results_file))[1]

      progress.set(5, True)
      progress.format = "Finishing"
      pya.Application.instance().main_window().repaint()
      
    elif version.find("3.") > -1:
      import subprocess
      cmd = subprocess.check_output

      progress.format = "Uploading Layout and Scripts"      
      progress.set(2, True)
      pya.Application.instance().main_window().repaint()
      
      try:
        out += cmd('ssh drc "mkdir -p %s"' % (remote_path), shell=True)
        out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, local_file, remote_path), shell=True)
        out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, 'run_calibre', remote_path), shell=True)
        out += cmd('cd "%s" && scp "%s" drc:%s' % (local_path, 'drc.cal', remote_path), shell=True)

        progress.format = "Checking Layout for Errors"
        progress.set(3, True)
        pya.Application.instance().main_window().repaint()

        out += cmd('ssh drc "cd %s && source run_calibre"' % (remote_path), shell=True)
      
        progress.format = "Downloading Results"
        progress.set(4, True)
        pya.Application.instance().main_window().repaint()
      
        out += cmd('cd "%s" && scp drc:%s "%s"' % (local_path, remote_path + "/drc.rve", results_file), shell=True)
      except subprocess.CalledProcessError as e:
        out += '\nError running ssh or scp commands. Please check that these programs are available.\n'
        out += str(e.output)
#        if e.output.startswith('error: {'):
#          import json
#          error = json.loads(e.output[7:])
#          print (error['code'])
#          print (error['message'])
      progress.format = "Finishing"
      progress.set(5, True)

    print(out)
    progress._destroy()
    if os.path.exists(results_pathfile):
      rdb_i = lv.create_rdb("Calibre Verification")
      rdb = lv.rdb(rdb_i)
      rdb.load (results_pathfile)
      rdb.top_cell_name = cell.name
      rdb_cell = rdb.create_cell(cell.name)
      lv.show_rdb(rdb_i, lv.active_cellview().cell_index)
    else:
      pya.MessageBox.warning("Errors", "Something failed during the server Calibre DRC check: %s" % out,  pya.MessageBox.Ok)

    pya.Application.instance().main_window().update()
    lv.commit()
    
def auto_coord_extract():
  from .utils import get_technology
  TECHNOLOGY = get_technology()
  def gen_ui():
    global wdg
    if 'wdg' in globals():
      if wdg is not None and not wdg.destroyed():
        wdg.destroy()
    global wtext
  
    def button_clicked(checked):
      """ Event handler: "OK" button clicked """
      wdg.destroy()
  
    wdg = pya.QDialog(pya.Application.instance().main_window())
  
    wdg.setAttribute(pya.Qt.WA_DeleteOnClose)
    wdg.setWindowTitle("SiEPIC-Tools: Automated measurement coordinate extraction")
  
    wdg.resize(1000, 500)
    wdg.move(1, 1)
  
    grid = pya.QGridLayout(wdg)
  
    windowlabel1 = pya.QLabel(wdg)
    windowlabel1.setText("output:")
    wtext = pya.QTextEdit(wdg)
    wtext.enabled = True
    wtext.setText('')
  
    ok = pya.QPushButton("OK", wdg)
    ok.clicked(button_clicked)   # attach the event handler
#    netlist = pya.QPushButton("Save", wdg) # not implemented
  
    grid.addWidget(windowlabel1, 0, 0, 1, 3)
    grid.addWidget(wtext, 1, 1, 3, 3)
#    grid.addWidget(netlist, 4, 2)
    grid.addWidget(ok, 4, 3)
  
    grid.setRowStretch(3, 1)
    grid.setColumnStretch(1, 1)
  
    wdg.show()
  
  # Create a GUI for the output:
  gen_ui()
  wtext.insertHtml('<br>* Automated measurement coordinates:<br><br>')
  
  # Find the automated measurement coordinates:
  from .utils import find_automated_measurement_labels
  cell = pya.Application.instance().main_window().current_view().active_cellview().cell
  text_out,opt_in = find_automated_measurement_labels(cell)
  wtext.insertHtml (text_out)

def calculate_area():
  from .utils import get_technology
  TECHNOLOGY = get_technology()

  lv = pya.Application.instance().main_window().current_view()
  if lv == None:
    raise Exception("No view selected")
  ly = lv.active_cellview().layout()
  if ly == None:
    raise Exception("No active layout")
  cell = lv.active_cellview().cell
  if cell == None:
    raise Exception("No active cell")
    
  total = cell.each_shape(ly.layer(TECHNOLOGY['FloorPlan'])).__next__().polygon.area()
  area = 0
  itr = cell.begin_shapes_rec(ly.layer(TECHNOLOGY['LayerSi']))
  while not itr.at_end():
    area += itr.shape().area()
    itr.next()
  print(area/total)
  
  area = 0
  itr = cell.begin_shapes_rec(ly.layer(TECHNOLOGY['SiEtch1']))
  while not itr.at_end():
    area += itr.shape().area()
    itr.next()
  print(area/total)
  
  area = 0
  itr = cell.begin_shapes_rec(ly.layer(TECHNOLOGY['SiEtch2']))
  while not itr.at_end():
    area += itr.shape().area()
    itr.next()
  print(area/total)



"""
SiEPIC-Tools: Trim Netlist
by Jaspreet Jhoja (c) 2016-2017

This Python function facilitates trimming of netlist based on a selected component. 
Version history:

Jaspreet Jhoja           2017/12/29
 - Initial version
"""
# Inputs, and example of how to generate them:
# nets, components = topcell.identify_nets()
# selected_component = components[5]   (elsewhere the desired component is selected)

def trim_netlist (nets, components, selected_component, verbose=None):
  selected = selected_component
  #>17        <2
  #nets[0].pins[0].component.idx
  trimmed_net = []
  net_idx = [[each.pins[0].component.idx,each.pins[1].component.idx] for each in nets]
  len_net_idx = len(net_idx)
  count= 0
  trimmed_nets, trimmed_components = [],[]
  while count< (len_net_idx - 1):
      for i in range(count + 1, len_net_idx): #i keep track of nets from next net to last net 
          first_set = set(net_idx[count])     #first set is formed of elements from current to backwards
          second_set = set(net_idx[i])        # second set is formed of elements from current + 1 to forward
          if len(first_set.intersection(second_set)) > 0:  #if there are common elements between two sets
              net_idx.pop(i)                               #remove the nets from the list
              net_idx.pop(count)                           #remove the count net as well
              net_idx.append(list(first_set.union(second_set)))  #merged them and add to the list                  
              len_net_idx -= 1 #2 removed 1 added so reduce 1
              count-= 1 #readjust count as the elements have shifted to left
              break
      count+= 1
  for net in net_idx:
    if(selected.idx in net):
      trimmed_components = [each for each in components if each.idx in net]
      trimmed_nets = [each for each in nets if (each.pins[0].component.idx in net or each.pins[1].component.idx in net)]
      if verbose:
        print("success - netlist trimmed")

  return trimmed_nets, trimmed_components
  


'''
Verification:

Limitations:
- we assume that the layout was created by SiEPIC-Tools in KLayout, that PCells are there,
  and that the layout hasn't been flattened. This allows us to isolate individual components,
  and get their parameters. Working with a flattened layout would be harder, and require:
   - reading parameters from the text labels (OK)
   - find_components would need to look within the DevRec layer, rather than in the selected cell
   - when pins are connected, we have two overlapping ones, so detecting them would be problematic;
     This could be solved by putting the pins inside the cells, rather than sticking out.

'''
def layout_check(cell = None, verbose=False):
  if verbose:
    print("*** layout_check()")

  from . import _globals
  from .utils import get_technology, find_paths, find_automated_measurement_labels, angle_vector
  TECHNOLOGY = get_technology()
  dbu=TECHNOLOGY['dbu']

  lv = pya.Application.instance().main_window().current_view()
  if lv == None:
    raise Exception("No view selected")
  if cell is None:
    ly = lv.active_cellview().layout() 
    if ly == None:
      raise Exception("No active layout")
    cell = lv.active_cellview().cell
    if cell == None:
      raise Exception("No active cell")
    cv = lv.active_cellview()
  else:
    ly = cell.layout()

  # Get the components and nets for the layout
  nets, components = cell.identify_nets(verbose=False)
  if verbose:
    print ("* Display list of components:" )
    [c.display() for c in components]

  # Create a Results Database
  rdb_i = lv.create_rdb("SiEPIC-Tools Verification: %s technology" % TECHNOLOGY['technology_name'])
  rdb = lv.rdb(rdb_i)
  rdb.top_cell_name = cell.name
  rdb_cell = rdb.create_cell(cell.name)

  # Waveguide checking
  rdb_cell = next(rdb.each_cell())
  rdb_cat_id_wg = rdb.create_category("Waveguide")
  rdb_cat_id_wg_path = rdb.create_category(rdb_cat_id_wg, "Path")
  rdb_cat_id_wg_path.description = "Waveguide path: Only 2 points allowed in a path. Convert to a Waveguide if necessary."
  rdb_cat_id_wg_radius = rdb.create_category(rdb_cat_id_wg, "Radius")
  rdb_cat_id_wg_radius.description = "Not enough space to accommodate the desired bend radius for the waveguide."
  rdb_cat_id_wg_bendpts = rdb.create_category(rdb_cat_id_wg, "Bend points")
  rdb_cat_id_wg_bendpts.description = "Waveguide bend should have more points per circle."
  rdb_cat_id_wg_manhattan = rdb.create_category(rdb_cat_id_wg, "Manhattan")
  rdb_cat_id_wg_manhattan.description =  "The first and last waveguide segment need to be Manhattan (vertical or horizontal) so that they can connect to device pins."

  # Component checking
  rdb_cell = next(rdb.each_cell())
  rdb_cat_id_comp = rdb.create_category("Component")
  rdb_cat_id_comp_flat = rdb.create_category(rdb_cat_id_comp, "Flattened component")
  rdb_cat_id_comp_flat.description = "SiEPIC-Tools Verification, Netlist extraction, and Simulation only functions on hierarchical layouts, and not on flattened layouts.  Add to the discussion here: https://github.com/lukasc-ubc/SiEPIC-Tools/issues/37"
  rdb_cat_id_comp_overlap = rdb.create_category(rdb_cat_id_comp, "Overlapping component")
  rdb_cat_id_comp_overlap.description = "Overlapping components (defined as overlapping DevRec layers; touch is ok)"

  # Connectivity checking
  rdb_cell = next(rdb.each_cell())
  rdb_cat_id = rdb.create_category("Connectivity")
  rdb_cat_id_discpin = rdb.create_category(rdb_cat_id, "Disconnected pin")
  rdb_cat_id_discpin.description = "Disconnected pin"
  rdb_cat_id_mismatchedpin = rdb.create_category(rdb_cat_id, "Mismatched pin")
  rdb_cat_id_mismatchedpin.description = "Mismatched pin widths"

  # Simulation checking
  rdb_cell = next(rdb.each_cell())
  rdb_cat_id = rdb.create_category("Simulation")
  rdb_cat_id_sim_nomodel = rdb.create_category(rdb_cat_id, "Missing compact model")
  rdb_cat_id_sim_nomodel.description = "A compact model for this component was not found. Possible reasons: 1) Please run SiEPIC | Simulation | Setup Lumerical INTERCONNECT and CML, to make sure that the Compact Model Library is installed in INTERCONNECT, and that KLayout has a list of all component models. 2) the library does not have a compact model for this component. "

  # Design for Test checking
  from SiEPIC.utils import load_DFT
  DFT=load_DFT()
  if DFT:
    if verbose:
      print(DFT)
    rdb_cell = next(rdb.each_cell())
    rdb_cat_id = rdb.create_category("Design for test")
    rdb_cat_id_optin_unique = rdb.create_category(rdb_cat_id, "opt_in label: same")
    rdb_cat_id_optin_unique.description = "Automated test opt_in labels should be unique."
    rdb_cat_id_optin_missing = rdb.create_category(rdb_cat_id, "opt_in label: missing")
    rdb_cat_id_optin_missing.description = "Automated test opt_in labels are required for measurements."
    rdb_cat_id_optin_toofar = rdb.create_category(rdb_cat_id, "opt_in label: too far away")
    rdb_cat_id_optin_toofar.description = "Automated test opt_in labels must be placed at the tip of the grating coupler, namely near the (0,0) point of the cell."
    rdb_cat_id_GCpitch = rdb.create_category(rdb_cat_id, "Grating Coupler pitch")
    rdb_cat_id_GCpitch.description = "Grating couplers must be on a %s micron pitch, vertically arranged." % (float(DFT['design-for-test']['grating-couplers']['gc-pitch']))
    rdb_cat_id_GCorient = rdb.create_category(rdb_cat_id, "Grating coupler orientation")
    rdb_cat_id_GCorient.description = "The grating coupler is not oriented (rotated) the correct way for automated testing."
    rdb_cat_id_GCarrayconfig = rdb.create_category(rdb_cat_id, "Fibre array configuration")
    rdb_cat_id_GCarrayconfig.description = "Circuit must be connected such that there is at most %s Grating Couplers above the opt_in label (laser injection port) and at most %s Grating Couplers below the opt_in label" % (int(DFT['design-for-test']['grating-couplers']['detectors-above-laser']), int(DFT['design-for-test']['grating-couplers']['detectors-below-laser']))
  else:
    if verbose:
      print('  No DFT rules found.')

  paths = find_paths(TECHNOLOGY['Waveguide'], cell = cell)
  for p in paths:
    if verbose:
      print("%s, %s" % (type(p), p) )
    # Check for paths with > 2 vertices
    Dpath = p.to_dtype(dbu)
    if Dpath.num_points() > 2:
      rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_wg_path.rdb_id())
      rdb_item.add_value(pya.RdbItemValue(Dpath.polygon()))

  for i in range(0,len(components)):
    c=components[i]
    # the following only works for layouts where the Waveguide is still a PCells (not flattened)
    # basic_name is assigned in Cell.find_components, by reading the PCell parameter
    # if the layout is flattened, we don't have an easy way to get the path
    # it could be done perhaps as a parameter (points)
    if c.basic_name == "Waveguide" and c.cell.is_pcell_variant():
      Dpath =  c.cell.pcell_parameters_by_name()['path']
      radius = c.cell.pcell_parameters_by_name()['radius']
      if verbose:
        print(" - Waveguide: cell: %s, %s" % (c.cell.name, radius) )

      # Radius check:
      if not Dpath.radius_check(radius):
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_wg_radius.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( Dpath ) )

      # Check for waveguides with too few bend points

      # Check if waveguide end segments are Manhattan; this ensures they can connect to a pin
      if not Dpath.is_manhattan():
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_wg_manhattan.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( DPath ) )

    if c.basic_name == "Flattened":
      if verbose:
        print(" - Component: Flattened: %s" % (c.polygon) )
      rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_comp_flat.rdb_id())
      rdb_item.add_value(pya.RdbItemValue( c.polygon.to_dtype(dbu) ) )

    # check all the component's pins to check if they are assigned a net:
    for pin in c.pins:
      if pin.type == _globals.PIN_TYPES.OPTICAL and pin.net.idx == None:
        # disconnected optical pin 
        if verbose:
          print( " - Found disconnected pin, type %s, at (%s)"  % (pin.type, pin.center) )
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_discpin.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( pin.path.to_dtype(dbu) ) )
      
    # Verification: overlapping components (DevRec)
      # automatically takes care of waveguides crossing other waveguides & components
    # Region: put in two DevRec polygons (in raw), measure area, merge, check if are is the same
    #  checks for touching but not overlapping DevRecs
    for i2 in range(i+1,len(components)):
      c2=components[i2]
      r = pya.Region([c.polygon, c2.polygon])
      r.merged_semantics=False
      area_raw = r.area()
      r.merged_semantics=True
      area_merged = r.area()
      if abs(area_merged - area_raw) > 3:  # I don't know why they are sometimes different by exactly 3... other times exacty the same.
        from .utils import advance_iterator 
        polygon_merged = advance_iterator(r.each_merged())
#        polygon_merged = r.each_merged().next()
        if verbose:
          print( " - Found overlapping components: %s, %s. Area comparison: %s, %s"  % (c.component, c2.component, area_raw, area_merged) )
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_comp_overlap.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( polygon_merged.to_dtype(dbu) ) )
    
    if DFT:
    # DFT verification
      # GC facing the right way
      if c.basic_name:
        ci = c.basic_name #.replace(' ','_').replace('$','_')
        gc_orientation_error = False
        for gc in DFT['design-for-test']['grating-couplers']['gc-orientation'].keys():
          if ci == gc and c.trans.angle != int(DFT['design-for-test']['grating-couplers']['gc-orientation'][gc]):
            gc_orientation_error = True
        if gc_orientation_error:
          if verbose:
            print( " - Found DFT error, GC facing the wrong way: %s, %s"  % (c.component, c.trans.angle) )
          rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_GCorient.rdb_id())
          rdb_item.add_value(pya.RdbItemValue( c.polygon.to_dtype(dbu) ) )
    
    # Pre-simulation check: do components have models?
    if not c.has_model():
      if verbose:
        print( " - Missing compact model, for component: %s"  % (c.component) )
      rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_sim_nomodel.rdb_id())
      rdb_item.add_value(pya.RdbItemValue( c.polygon.to_dtype(dbu) ) )


  if DFT:
  # DFT verification

    # opt_in labels missing
    text_out, opt_in = find_automated_measurement_labels(cell)
    if len(opt_in) == 0:
      rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_optin_missing.rdb_id())
      rdb_item.add_value(pya.RdbItemValue( pya.Polygon(cell.bbox()).to_dtype(dbu) ) )
    # opt_in labels
    for ti1 in range(0,len(opt_in)):
      t = opt_in[ti1]['Text']
      box_s = 1000
      box = pya.Box(t.x-box_s, t.y-box_s, t.x+box_s, t.y+box_s)
      # opt_in labels check for unique
      for ti2 in  range(ti1+1, len(opt_in)):
        if opt_in[ti1]['opt_in'] == opt_in[ti2]['opt_in']:
          if verbose:
            print( " - Found DFT error, non unique text labels: %s, %s, %s"  % (t.string, t.x, t.y) )
          rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_optin_unique.rdb_id())
          rdb_item.add_value(pya.RdbItemValue( pya.Polygon(box).to_dtype(dbu) ) )
  
      # find the GC closest to the opt_in label. 
      
      from ._globals import KLAYOUT_VERSION
      components_sorted = sorted([c for c in components if [p for p in c.pins if p.type == _globals.PIN_TYPES.OPTICALIO]], key=lambda x: x.trans.disp.to_p().distance(pya.Point(t.x, t.y).to_dtype(1)))
      # GC too far check:
      dist_optin_c = components_sorted[0].trans.disp.to_p().distance(pya.Point(t.x, t.y).to_dtype(1))
      if verbose:
        print( " - Found opt_in: %s, nearest GC: %s.  Locations: %s, %s. distance: %s"  % (opt_in[ti1]['Text'], components_sorted[0].instance,  components_sorted[0].center, pya.Point(t.x, t.y), dist_optin_c*dbu) )
      if dist_optin_c > float(DFT['design-for-test']['opt_in']['max-distance-to-grating-coupler'])*1000:
        if verbose:
          print( " - opt_in label too far from the nearest grating coupler: %s, %s"  % (components_sorted[0].instance, opt_in[ti1]['opt_in']) )
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_optin_toofar.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( pya.Polygon(box).to_dtype(dbu) ) )
        
      # starting with each opt_in label, identify the sub-circuit, then GCs, and check for GC spacing
      trimmed_nets, trimmed_components = trim_netlist (nets, components, components_sorted[0])
      detector_GCs = [ c for c in trimmed_components if [p for p in c.pins if p.type == _globals.PIN_TYPES.OPTICALIO] if (c.trans.disp - components_sorted[0].trans.disp).to_p()  != pya.DPoint(0,0)]
      if verbose:
        print("   N=%s, detector GCs: %s" %  (len(detector_GCs), [c.display() for c in detector_GCs]) )
      vect_optin_GCs = [(c.trans.disp - components_sorted[0].trans.disp).to_p() for c in detector_GCs]
      for vi in range(0,len(detector_GCs)):
        if round(angle_vector(vect_optin_GCs[vi])%180)!=int(DFT['design-for-test']['grating-couplers']['gc-array-orientation']):
          if verbose:
            print( " - DFT GC pitch or angle error: angle %s, %s"  % (round(angle_vector(vect_optin_GCs[vi])%180), opt_in[ti1]['opt_in']) )
          rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_GCpitch.rdb_id())
          rdb_item.add_value(pya.RdbItemValue( detector_GCs[vi].polygon.to_dtype(dbu) ) )
            
      # find the GCs in the circuit that don't match the testing configuration
      for d in list(range(int(DFT['design-for-test']['grating-couplers']['detectors-above-laser'])+1,0,-1)) + list(range(-1, -int(DFT['design-for-test']['grating-couplers']['detectors-below-laser'])-1,-1)):
        if pya.DPoint(0,d*float(DFT['design-for-test']['grating-couplers']['gc-pitch'])*1000) in vect_optin_GCs:
          del_index = vect_optin_GCs.index(pya.DPoint(0,d*float(DFT['design-for-test']['grating-couplers']['gc-pitch'])*1000))
          del vect_optin_GCs[del_index]
          del detector_GCs[del_index]
      for vi in range(0, len(vect_optin_GCs)):
        if verbose:
          print( " - DFT GC array config error: %s, %s"  % (components_sorted[0].instance, opt_in[ti1]['opt_in']) )
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_GCarrayconfig.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( detector_GCs[vi].polygon.to_dtype(dbu) ) )
  
      
    # GC spacing between separate GC circuits (to avoid measuring the wrong one)
  

  for n in nets:
    # Verification: optical pin width mismatches
    if n.type == _globals.PIN_TYPES.OPTICAL and not n.idx == None:
      pin_paths = [p.path for p in n.pins]
      if pin_paths[0].width != pin_paths[-1].width:
        if verbose:
          print( " - Found mismatched pin widths: %s"  % (pin_paths[0]) )
        r = pya.Region([pin_paths[0].to_itype(1).polygon(), pin_paths[-1].to_itype(1).polygon()])
        polygon_merged = advance_iterator(r.each_merged())
        rdb_item = rdb.create_item(rdb_cell.rdb_id(),rdb_cat_id_mismatchedpin.rdb_id())
        rdb_item.add_value(pya.RdbItemValue( polygon_merged.to_dtype(dbu) ) )
    

      
  #displays results in Marker Database Browser, using Results Database (rdb)
  if rdb.num_items() > 0:
    v = pya.MessageBox.warning("Errors", "%s layout errors detected.  \nPlease review errors using the 'Marker Database Browser'." % rdb.num_items(), pya.MessageBox.Ok)
    lv.show_rdb(rdb_i, cv.cell_index)
  else:
    v = pya.MessageBox.warning("Errors", "No layout errors detected.", pya.MessageBox.Ok)


  
''' 
Open all PDF files using an appropriate viewer
'''
def open_PDF_files(files,files_list):
  import sys
  if sys.platform.startswith('darwin'):
    import commands
    # open all the files in a single Preview application. 
    # open in one window with tabs: https://support.apple.com/en-ca/guide/mac-help/mchlp2469
    # System Preferences - Dock - Prefer tabs when opening documents - Always
    runcmd = '/usr/bin/open -n -a /Applications/Preview.app %s' % files
    print("Running in shell: %s" % runcmd)
    print(commands.getstatusoutput(runcmd))
  if sys.platform.startswith('win'):
    import os
    for f in files_list:
      os.startfile(f)
'''
Open the folder using an appropriate file finder / explorer
'''
def open_folder(folder):
  import sys
  if sys.platform.startswith('darwin'):
    import commands
    runcmd = '/usr/bin/open %s' % folder
    print("Running in shell: %s" % runcmd)
    print(commands.getstatusoutput(runcmd))

  if sys.platform.startswith('win'):
    import subprocess
    print("running in windows explorer, %s" % folder)
    print(subprocess.Popen(r'explorer /select,"%s"' % folder))

'''
User to select opt_in labels, either:
 - Text object selection in the layout
 - GUI with drop-down menu from all labels in the layout
 - argument to the function, opt_in_selection_text, array of opt_in labels (strings)
''' 
def user_select_opt_in(verbose=None, option_all=True, opt_in_selection_text=[]):
  from .utils import find_automated_measurement_labels
  text_out,opt_in = find_automated_measurement_labels()
  if not opt_in:
    print (' No opt_in labels found in the layout')
    return False, False
  
  # optional argument to this function
  if not opt_in_selection_text:
  
    # First check if any opt_in labels are selected  
    from .utils import selected_opt_in_text
    oinstpaths = selected_opt_in_text()
    for oi in oinstpaths:
      opt_in_selection_text.append (oi.shape.text.string)
    
    if opt_in_selection_text:
      if verbose:
        print(' user selected opt_in labels')
    else:
      # If not, scan the cell and find all the labels
      if verbose:
        print(' starting GUI to select opt_in labels')
  
      # GUI to ask which opt_in measurement to fetch
      opt_in_labels = [o['opt_in'] for o in opt_in]
      if option_all:
        opt_in_labels.insert(0,'All opt-in labels')
      opt_in_selection_text = pya.InputDialog.ask_item("opt_in selection", "Choose one of the opt_in labels, to fetch experimental data.",  opt_in_labels, 0)
      if not opt_in_selection_text: # user pressed cancel
        if verbose:
          print (' user cancel!')
        return False, False
      if opt_in_selection_text == 'All opt-in labels':
        opt_in_selection_text = [o['opt_in'] for o in opt_in]
        if verbose:
          print('  selecting all opt_in labels' )
      else:
        opt_in_selection_text = [opt_in_selection_text]

  # find opt_in Dict entries matching the opt_in text labels
  opt_in_dict = []
  for o in opt_in: 
    for t in opt_in_selection_text:
      if o['opt_in'] == t:
        opt_in_dict.append(o)

  return opt_in_selection_text, opt_in_dict

'''
Fetch measurement data from GitHub

Identify opt_in circuit, using one of:
 - selected opt_in Text objects
 - GUI
    - All - first option
    - Individual - selected

Query GitHub to find measurement data for opt_in label(s)

Get data, one of:
 - All
 - Individual
'''
def fetch_measurement_data_from_github(verbose=None, opt_in_selection_text=[]):
  import pya, tempfile
  from .github import github_get_filenames, github_get_files, github_get_file
  
  if verbose:
    print('Fetch measurement data from GitHub')

  tmp_folder = tempfile.mkdtemp()
  if opt_in_selection_text:
    folder_flatten_option = True
  else:
    folder_flatten_option = None

  if opt_in_selection_text:
    include_path=False

  from .scripts import user_select_opt_in
  opt_in_selection_text, opt_in_dict = user_select_opt_in(verbose=verbose, opt_in_selection_text=opt_in_selection_text)
  
  if verbose:
    print(' opt_in labels: %s' % opt_in_selection_text )
    print(' Begin looping through labels')
    
  all_measurements = 0
  savefilepath = []
  
  # Loop through the opt_in text labels
  for ot in opt_in_selection_text:

    fields = ot.split("_")
    search_for = ''
    for i in range(4,min(7,len(fields))):
      search_for += fields[i]+'_'
    if verbose:
      print("  searching for: %s" % search_for)

    files = github_get_filenames(extension='pdf', user='lukasc-ubc', repo='edX-Phot1x', filesearch=search_for, verbose=verbose)

    if len(files) == 0:
      print (' measurement not found!')
      return
      
    elif len(files) == 1:
      measurements_text = files[0][1].replace('%20',' ')
    elif len(files) > 1:
      if all_measurements == 0:
        # GUI to ask which opt_in measurement to fetch
        measurements = [f[1].replace('%20',' ') for f in files]
        measurements.insert(0,'All measurements')
        measurements_text = pya.InputDialog.ask_item("opt_in selection", "Choose one of the data files for opt_in = %s, to fetch experimental data.\n" % search_for,  measurements, 0)
        if not measurements_text: # user pressed cancel
          if verbose:
            print (' user cancel!')
          return 
        if measurements_text == 'All measurements':
          if verbose:
            print ('  all measurements')
          all_measurements = 1
    
    if not folder_flatten_option:
      # GUI to ask if we want to keep the folder tree
      options = ['Flatten folder tree','Replicate folder tree']
      folder_flatten_option = pya.InputDialog.ask_item("folder tree", "Do you wish to place all files in the same folder (flatten folder tree), or recreate the folder tree structure?",  options, 0)
      if folder_flatten_option == 'Replicate folder tree': 
        include_path=True
      else:
        include_path=False

    # Download file(s)
    if all_measurements == 1:
      savefilepath1  = github_get_files(user='lukasc-ubc', repo='edX-Phot1x',filename_search=search_for, save_folder=tmp_folder,  include_path=include_path, verbose=verbose)
      savefilepath += savefilepath1
    else: # find the single file to download
      for f in files:
        if f[1] == measurements_text.replace(' ','%20'):
          file_selection = f
      if verbose:
        print('   File selection: %s' % file_selection)
      savefilepath1 = github_get_file(user='lukasc-ubc', repo='edX-Phot1x', filename_search=file_selection[0], filepath_search=file_selection[1], include_path=include_path, save_folder=tmp_folder, verbose=verbose) 
      savefilepath += [savefilepath1]

    # this launches open_PDF once for each opt_in label:
    if 0 and savefilepath:  
      if verbose:
        print('All files for opt_in %s: %s' % (savefilepath1) )
      
      files = ''
      depth = lambda L: isinstance(L, list) and max(map(depth, L))+1
      if depth(savefilepath1):
        for s in savefilepath1:
          files += s + ' '        
      else:
        files = savefilepath1
        
      open_PDF_files(files)

  # this launches open_PDF once for all files at the end:
  if 1 and savefilepath:
    if verbose:
      print('All files: %s' % (savefilepath1) )

    files = ''
    for s in savefilepath:
      files += s + ' '        
    
    if verbose or not opt_in_selection_text:
      open_PDF_files(files, savefilepath)
      open_folder(tmp_folder)

  if not opt_in_selection_text:
    warning = pya.QMessageBox()
    warning.setStandardButtons(pya.QMessageBox.Ok)
    if savefilepath:  
      warning.setText("Measurement Data: successfully downloaded files.")
    else:
      warning.setText("Measurement Data: 0 files downloaded.")
    pya.QMessageBox_StandardButton(warning.exec_())
            
  return files, savefilepath


'''
Identify opt_in circuit, using one of:
 - selected opt_in Text objects
 - GUI
    - All - first option
    - Individual - selected

Fetch measurement data from GitHub
Run simulation

Plot data together

'''

def measurement_vs_simulation(verbose=None):
  import pya, tempfile
  from .scripts import fetch_measurement_data_from_github
  from .scripts import user_select_opt_in
  from lumerical.interconnect import circuit_simulation
  
  
  if verbose:
    print('measurement_vs_simulation()')

  opt_in_selection_text, opt_in_dict = user_select_opt_in(verbose=verbose)
    
  if verbose:
    print(' opt_in labels: %s' % opt_in_selection_text )
    print(' Begin looping through labels')
    
  # Loop through the opt_in text labels
  for ot in opt_in_selection_text:
      
      # Fetch github data:
      files, savefilepath = fetch_measurement_data_from_github(verbose=verbose, opt_in_selection_text=[ot])
        
      # simulate:
      circuit_simulation(verbose=verbose,opt_in_selection_text=[ot], matlab_data_files=savefilepath)

  warning = pya.QMessageBox()
  warning.setStandardButtons(pya.QMessageBox.Ok)
  if savefilepath:
    warning.setText("Measurement versus Simulation: successfully downloaded files and simulated.")
  else:
    warning.setText("Measurement Data: 0 files downloaded.")
  pya.QMessageBox_StandardButton(warning.exec_())
            
  return files, savefilepath
