import dspace
import dspace.plotutils
import dspace.display

from distutils.version import LooseVersion, StrictVersion

import IPython

if StrictVersion(IPython.__version__) < StrictVersion('4.0.0'):
    from IPython.html.widgets import interact, interactive, fixed
    from IPython.html.widgets import HTMLWidget as HTML
    from IPython.html.widgets import TabWidget as Tab
    from IPython.html.widgets import CheckboxWidget as Checkbox
    from IPython.html.widgets import ButtonWidget as Button
    from IPython.html.widgets import ContainerWidget as Box
    from IPython.html.widgets import TextWidget as Text
    from IPython.html.widgets import TextareaWidget as Textarea
    from IPython.html.widgets import PopupWidget as Popup
    VBox = Box
    HBox = Box
else:
    from ipywidgets import *
    from popup import Popup as PopupWidget
    def Popup(children=[], **kwargs):
        return PopupWidget(children=[VBox(children=children)], **kwargs)

    
from IPython.display import clear_output, display, Latex

import matplotlib.pyplot as plt

import cStringIO
from matplotlib.backends.backend_agg import FigureCanvasAgg  

from system_widget import DisplaySystem
from symbols_widget import EditSymbols
from cases_widget import CasesTable
from case_widget import CaseReport
from co_localize_widget import CaseColocalization
from figures_widget import MakePlot, DisplayFigures
from tables_widget import DisplayTables
from parameters_widget import EditParameters

import cPickle as pickle
import base64

from os import listdir
from os.path import isfile, join


class WidgetSavedData(object):
   
    @staticmethod
    def load_widget_data(interactive, version=''):
        
        name = interactive.name
        version = interactive.version
        if version == '':
            files = [f for f in listdir('.') if isfile(join('.',f))]
            files = [f.split('-V') for f in files if f.startswith(interactive.name) and f.endswith('.dsipy')]
            versions = [LooseVersion(f[1].strip('.dsipy')) for f in files if len(f) > 1]
            if len(versions) == 0:
                version = ''
            else:
                version = '-V'+str(max(versions))
        else:
            version = '-V' + version
        file_name = name+version+'.dsipy'
        f = open(file_name, 'r')
        saved_data = pickle.load(f)
        f.close()
        figure_data = saved_data.saved['figure_data']
        
        figure_data = [tuple([base64.b64decode(i[0])] + list(i[1:])) for i in figure_data]
        saved_data.saved['figure_data'] = figure_data
        interactive.__dict__.update(saved_data.saved)
        
    
    def __init__(self, interactive):
        setattr(self, 'saved', {})
        save_fields = ['ds', 
                       'equations',
                       'name',
                       'version',
                       'pvals',
                       'cyclical',
                       'codominance',
                       'auxiliary',
                       'constraints',
                       'table_data',
                       'symbols',
                       'options',]
        self.saved.update({i:interactive.__dict__[i] for i in save_fields if i in interactive.__dict__})
        figure_data = interactive.figure_data
        figure_data = [tuple([base64.b64encode(i[0])] + list(i[1:])) for i in figure_data]
        self.saved['figure_data'] = figure_data
        
    def save_data(self):
        version = self.saved['version']
        if version != '':
            version = '-V'+self.saved['version']
        f = open(self.saved['name']+version+'.dsipy', 'w')
        pickle.dump(self, f)
        f.close() 
                       

class InteractiveInput(object):
    
    def __init__(self, name='', version='', equations=None, parameters=None,
                 get_parameters=None, auxiliary_variables=[], constraints=[],
                 symbols={}, resolve_cycles=False, resolve_codominance=False,
                 centered_axes=False, xaxis=None, yaxis=None, recast=True,
                 x_range=[1e-3, 1e3], y_range=[1e-3, 1e3],
                 zlim=None, by_signature=False, kinetic_orders=None,
                 included_cases=None, biological_constraints=[], resolution=100,
                 **kwargs):
        ''' 
        '''
        setattr(self, 'ds', None)
        setattr(self, 'equations', [])
        setattr(self, 'name', name)
        setattr(self, 'version', version)
        setattr(self, 'pvals', None)
        setattr(self, 'cyclical', resolve_cycles)
        setattr(self, 'codominance', resolve_codominance)
        setattr(self, 'recast', recast)
        setattr(self, 'auxiliary', [])
        setattr(self, 'constraints', [])
        setattr(self, 'kinetic_orders', [])
        setattr(self, 'symbols', symbols)
        setattr(self, 'widget', Tab())
        setattr(self, 'figures', None)
        setattr(self, 'figure_data', [])
        setattr(self, 'tables', None)
        setattr(self, 'table_data', [])
        setattr(self, 'display_system', None)
        setattr(self, 'options', dict(kwargs))
        self.options.update(center_axes=centered_axes, 
                            xaxis=xaxis, yaxis=yaxis,
                            range_x=x_range, range_y=y_range, zlim=zlim, 
                            by_signature=by_signature, 
                            kinetic_orders=kinetic_orders, 
                            get_parameters=get_parameters,
                            included_cases=included_cases,
                            biological_constraints=biological_constraints,
                            resolution=resolution)
        if equations is not None:
            self.equations = equations
            if isinstance(equations, list) is False:
                self.equations = [equations]
        
        if auxiliary_variables is not None:
            self.auxiliary = auxiliary_variables
            if isinstance(auxiliary_variables, list) is False:
                self.auxiliary = [auxiliary_variables]
                
        if constraints is not None:
            self.constraints = constraints
            if isinstance(constraints, list) is False:
                self.constraints = [constraints]
                
        if parameters is not None:
            self.pvals = dspace.VariablePool(names = parameters.keys())
            self.pvals.update(parameters)
        self.root = VBox(children=[self.widget])
        display(self.root)   
        self.update_child('About', self.help_widget())
        self.update_child('Main Menu', self.edit_equations_widget())

        
    def set_defaults(self, key, value):
        self.options[key] = value
        
    def defaults(self, key):
        if key in self.options:
            return self.options[key]
        else:
            return None        
        
    def reload_widgets(self):
        self.widget = Tab()
        display(self.root)
        self.update_child('Main Menu', self.edit_equations_widget())
        if self.ds is None:
            return
        self.update_widgets()
        self.figures.load_widgets()
        
    def child_with_name(self, name):
        children = self.widget.children
        for i in xrange(len(children)):
            if children[i].description == name:
                return self.widget.children[i]
        return None
    
    def update_child(self, name, child, index=None):
        previous_children = self.widget.children
        children = [i for i in self.widget.children]
        added = False
        for i in xrange(len(children)):
            if children[i].description == name:
                self.widget._titles = {}
                old = children.pop(i)
                break
        if added is False:
            if child is not None:
                child.description = name
                children.append(child)
                index = len(children)-1
            else:
                index = 0
        self.widget.children = children
        for (i, child) in enumerate(children):
            self.widget.set_title(i, child.description)
        self.widget.selected_index = index
        
    def enumerate_phenotypes_menu(self, b):
        cases_table = CasesTable(self)
        return cases_table.cases_table_widget()
        
        
    def case_report_menu(self, b):
        case_report = CaseReport(self, 
                                 self.defaults('by_signature'))
        return case_report.create_case_widget()

    def co_localize_menu(self, b):
        case_report = CaseColocalization(self, 
                                         self.defaults('by_signature'))
        return case_report.colocalization_widget()
    
    def create_plot_menu(self, b):
        plot = MakePlot(self)
        return plot.create_plot_widget()
        
    def load_widget(self, b):
        self.name = str(b.name.value)
        self.version = str(self.version_field.value)
        saved = WidgetSavedData.load_widget_data(self)
        b.wi.visible = True
        if self.ds is None:
            return
        self.make_options_menu(b.button)
        self.update_widgets()
        self.figures.load_widgets()       
        self.tables.load_widgets()       
        ## b.version.value = self.version
        self.widget.selected_index = 0
        
    def save_widget_data(self, b):
        save_widget = SavePopupWidget(self)
        widget_container = save_widget.save_popup_widget()
        self.root.children = [self.widget, widget_container]
        self.widget.visible = False
                
    def modify_equations_widget(self, b):
        self.ds = None
        self.figure_data = []
        self.table_data = []
        self.widget.close()
        self.widget = Tab()
        display(self.root)   
        self.update_child('Main Menu', self.edit_equations_widget(editing=True))
        
    def make_options_menu(self, b):
        wi = b.wi
        b.visible = False
        b.name.visible = False
        b.load.visible = False
        actions = [('Enumerate Phenotypes', self.enumerate_phenotypes_menu),
                   ('Analyze Case', self.case_report_menu),
                   ('Co-localize Phenotypes', self.co_localize_menu),
                   ('Create Plot', self.create_plot_menu)]
        actions_h = HTML(value='<b>Actions</b>')
        options_h = HTML(value='<b>Options</b>')
        options = [('Edit Symbols', self.create_edit_symbols),
                   ('Edit Parameters', self.create_edit_parameters),
                   ('Save Data', self.save_widget_data)]
        actions_w = Tab()
        options_w = []
        for name, method in options:
            button = Button(description=name)
            button.on_click(method)
            ## button.version = b.version
            if method is None:
                button.disabled = True
            options_w.append(button)
        edit = Button(description='Modify System')
        edit.on_click(self.modify_equations_widget)
        warning = HTML()
        warning.value = '<font color="red"><b>Warning! Modifying system erases saved figures and tables.</b></font>'
        wi.children = [actions_h, actions_w] + [options_h] + options_w + [edit, warning]
        for title, method in actions:
            title, widget = method(self)
            children = [i for i in actions_w.children] + [widget]
            actions_w.children = children
            actions_w.set_title(len(children)-1, title)
        self.widget.selected_index = 1
        
        
    def update_widgets(self):
        self.display_system = DisplaySystem(self)
        self.display_system.create_system_widget()
        self.figures = DisplayFigures(self)
        self.figures.create_figures_widget()
        self.tables = DisplayTables(self)
        self.tables.create_tables_widget()
                
    def help_widget(self):
        about_str = ['<p style="text-align:justify;"><font color="darkblue">',
                     'You are using the Design Space Toolbox V2 Jupyter',
                     'Notebook-based widget, a graphical interface for',
                     'the Design Space Toolbox V2 created by Jason',
                     'Lomnitz in the laboratory of Michael A. Savageau.',
                     '<br><br>',
                     'This software has been created for the analysis',
                     'of mathematical models of biochemical systems.',
                     'This library deconstructs a model into a series of',
                     'sub-models that can be analyzed by applying a series',
                     'of numerical and symbolic methods.',
                     '<br><br>',
                     'To begin, please enter the information in the required',
                     'fields (marked by an "*") and optional fields.',
                     'The Name field is used to save and load a model',
                     'workspace,which includes the system equations, tables'
                     ' and figures.  The primary input into the widget are the',
                     'system equations, represented by a list of strings.',
                     '<br><br></font>',
                     'The equations must satisfy the following rules:<br>',
                     '1. Each equation has to be explicitly stated as:<br>',
                     '1.1 A differential equation, where the "." operator',
                     'denotes the derivative with respect to time.<br>',
                     '1.2 An algebraic constraint, where the left hand side',
                     'is either a variable or a mathematical expression.',
                     'Auxiliary variables associated with the cinstraint must',
                     'be explicitly defined (unless the left-hand side is the',
                     'auxiliary variable.',
                     '<br><br>',
                     '2. Multiplication is represented by the "*" operator.',
                     '<br><br>',
                     '3. Powers are represented by the "^" operator.',
                     '<br><br>',
                     '4. Architectural constraints are defined as inequalities,',
                     'where both sides of the inequality are products of',
                     'power-laws.<br><br>',
                     '</p>']
        report_str = ['<p style="text-align:center;">',
                      'This software is a research tool and as such there are',
                      'a number of known bugs and issues.  A complete list of',
                      'open issues can be found online in the',
                      '<a target="_blank"',
                      'href="https://bitbucket.org/jglomnitz/design-space-toolbox/issues?status=new&status=open">',
                      'Project Issue Tracker</a>.<br>',
                      '<font color="red"><b>If you found a new bug or would',
                      'like to request an enhancement that has not yet',
                      'been reported, please report it here:</b></font>',
                      '<a target="_blank"',
                      'href="https://bitbucket.org/jglomnitz/design-space-toolbox/issues/new?title=Issue%20name">',
                      'REPORT BUG</a>',      
                      '</p>']
                         
        html = HTML(value=' '.join(report_str)+' '.join(about_str))
        return VBox(children=[html])
        
    def edit_equations_widget(self, editing=False):
        kinetic_orders = self.options['kinetic_orders']
        if kinetic_orders is None:
            kinetic_orders = []
        name = Text(description='* Name', value=self.name)
        version = Text(description='Version', value=self.version)
        self.version_field = version
        equations=Textarea(description='* Equations',
                                         value='\n'.join(self.equations))
        aux=Textarea(description='Auxiliary Variables',
                                   value=', '.join(self.auxiliary))
        html = HTML(value='<b>Architectural Constraints</b>')
        constraints=Textarea(description='Parameters',
                             value=', '.join(self.constraints)
                             )
        options_html = HTML(value='<b>Additional Options</b>')
        cyclical = Checkbox(description='Check for Cycles',
                            value = self.cyclical)
        codominance = Checkbox(description='Check for Co-dominance',
                               value = self.codominance)
        recast = Checkbox(description='Recast Equations',
                               value = self.recast)
        replacements=Textarea(description='Kinetic Orders',
                              value=', '.join(
                               [i for i in kinetic_orders]))
        wi = VBox(children=[equations, 
                            aux, html,
                            constraints, replacements,
                            options_html, cyclical,
                            codominance,recast,
                            ])
        button = Button(value=False, 
                                      description='Create Design Space')
        button.on_click(self.make_design_space)
        button.equations = equations
        button.aux = aux
        button.constraints = constraints
        button.cyclical = cyclical
        button.codominance = codominance
        button.recast = recast
        button.replacements = replacements
        button.wi = wi
        button.name = name
        ## button.version = version
        load = Button(value=False, 
                      description='Load Data')
        load.on_click(self.load_widget)
        load.equations = equations
        ## load.version = version
        load.aux = aux
        load.constraints = constraints
        load.cyclical = cyclical
        load.codominance = codominance
        load.replacements = replacements
        load.wi = wi
        load.name = name
        load.button = button
        button.load = load
        edit_symbols = Button(value=False, description='Edit Symbols')
        edit_symbols.on_click(self.create_edit_symbols)
        edit_parameters = Button(value=False, description='Edit Parameters')
        edit_parameters.on_click(self.create_edit_parameters)
        button.edit_symbols = edit_symbols
        button.edit_parameters = edit_parameters
        edit_equations = VBox(description='Edit Equations', 
                              children=[name, version, wi, 
                                        edit_symbols,
                                        edit_parameters,
                                        button,
                                        load])
        wi.visible = False
        edit_symbols.visible = False
        edit_parameters.visible = False
        if self.ds is not None:
            wi.visible = True
            ## self.update_widgets()
            self.make_options_menu(button)
        if editing is True:
            self.make_design_space(button)
        return edit_equations  
        
    def make_design_space(self, b):
        if b.wi.visible == False:
            b.wi.visible = True
            b.description = 'Done'
            return
        self.version_field.visible = False
        self.equations = [i.strip() for i in str(b.equations.value).split('\n') if len(i.strip()) > 0]
        self.auxiliary = [i.strip() for i in str(b.aux.value).split(',') if len(i.strip()) > 0] 
        self.constraints = [i.strip() for i in str(b.constraints.value).split(',') if len(i.strip()) > 0] 
        self.cyclical = b.cyclical.value
        self.codominance = b.codominance.value
        self.recast = b.recast.value
        eq = dspace.Equations(self.equations,
                              auxiliary_variables=self.auxiliary, 
                              latex_symbols=self.symbols)
        if self.recast:
            eq = eq.recast()
        self.name = b.name.value
        constraints = self.constraints
        replacements = str(b.replacements.value).strip()
        self.options.update(kinetic_orders=str(b.replacements.value).split(','))
        if len(replacements) > 0:
            replacements = str(b.replacements.value).split(',')
            replacements = [[j.strip() for j in i.split('=')] for i in replacements] 
            parameter_dict = {i:j for i,j in replacements}
        else:
            parameter_dict = {}
        if len(constraints) == 0:
            constraints = None
        self.ds = dspace.DesignSpace(eq, name=b.name.value, 
                                     constraints=constraints,
                                     resolve_cycles=self.cyclical, 
                                     resolve_codominance=self.codominance,
                                     parameter_dict=parameter_dict)
        if self.pvals == None:
            self.pvals = dspace.VariablePool(
                          names=self.ds.independent_variables
                          )
        else:
            pvals = dspace.VariablePool(
                     names=self.ds.independent_variables
                     )
            for i in pvals:
                if i in self.pvals:
                    pvals[i] = self.pvals[i]
            self.pvals = pvals
        get_parameters = self.defaults('get_parameters')
        if get_parameters is not None:
             case = self.ds(get_parameters)
             self.pvals = case.valid_interior_parameter_set()
        self.symbols.update({i:i for i in self.ds.dependent_variables + self.ds.independent_variables if i not in self.symbols})
        self.ds.update_latex_symbols(self.symbols)
        self.update_widgets()
        self.make_options_menu(b)
    
    def create_edit_symbols(self, b):
        Edit = EditSymbols(self)
        Edit.edit_symbols_widget() 
               
    def create_edit_parameters(self, b):
        Edit = EditParameters(self)
        Edit.edit_parameters_widget()

class SavePopupWidget(object):
    
    def __init__(self, controller):
        
        setattr(self, 'controller', controller)
        
    def save_popup_widget(self):
        controller = self.controller
        save_button = Button(description='Save')
        cancel_button = Button(description='Cancel')
        name_field = Text(description='* Name', value=controller.name)
        version_field = Text(description='Version', 
                             value=controller.version)
        save_button.on_click(self.save_widget_data)
        save_button.name_field = name_field
        save_button.version_field = version_field
        cancel_button.on_click(self.cancel_save)
        self.save_data = VBox(description='Save Data',
                               children=[VBox(children=[
                                               HTML(value='<center width="100%"><b>Are you sure you want to save?</b></center>'),
                                               name_field,
                                               version_field,
                                               HBox(children=[
                                                     save_button, 
                                                     cancel_button])])])
        self.save_data.box_style = 'warning'
        self.save_data.overflow_x = 'auto'
        self.save_data.overflow_y = 'auto'
        self.save_data.width = '100vh'
        return self.save_data
    
    def save_widget_data(self, b):
        controller = self.controller
        controller.name = str(b.name_field.value)
        controller.version = str(b.version_field.value)
        self.save_data.box_style = 'success'
        self.save_data.children = [HTML(value='<center><b>Saving Data</b></center>')]
        save = WidgetSavedData(controller)
        save.save_data()
        controller.display_system.update_display()
        controller = self.controller
        controller.root.children = [controller.widget]
        controller.widget.visible = True
        
    def cancel_save(self, b):
        controller = self.controller
        controller.root.children = [controller.widget]
        controller.widget.visible = True
        
        
