''' Definition of the abstract model class.


'''
import itertools

from dspace.SWIG.dspace_interface import *
from dspace.variables import VariablePool
from dspace.models.base import Equations,Model
from dspace.models.gma import GMASystem
from dspace.models.ssystem import SSystem
from dspace.models.case import Case, CaseIntersection, CaseColocalization
from dspace.models.cyclicalcase import CyclicalCase
from dspace.expressions import Expression

def sort_cases(x, y):
    x = x.split('_')
    y = y.split('_')
    for i in xrange(min(len(x), len(y))):
        xi = int(x[i])
        yi = int(y[i])
        if xi < yi:
            return -1
        if xi > yi:
            return 1
    return 0


class DesignSpace(GMASystem):
    
    def __init__(self, equations,
                 parameter_dict=None, 
                 resolve_cycles=False,
                 constraints=None, match_Xi=None,
                 latex_symbols=None,
                 resolve_codominance=False,
                 **kwargs):
        ''' Initializes a new object with the input parameters for a routine
            analysis.
        
        
                 
        Args:
            equations (list): A list of equations in string format defining the 
                system to analyze.
        
        Kwargs:
            parameter_dict (dict): A dictionary of substrings and replacement
                strings to modify original equations.
            
            resolve_cycles (bool): A flag indicating if cycles should be
               automatically resolved. Setting this to true adds significant
               overhead.
        '''
        if parameter_dict is not None:
            equations = equations.replace_symbols(parameter_dict)
        super(DesignSpace, self).__init__(equations, match_Xi=match_Xi, 
                                          latex_symbols=latex_symbols, **kwargs)
        setattr(self, '_resolve_cycles', False)
        if constraints is not None:
            if isinstance(constraints, list) is False:
                constraints = [constraints]
            DSDesignSpaceAddConstraints(self._swigwrapper, constraints, len(constraints))
        if resolve_codominance is True:
            DSDesignSpaceSetResolveCoDominance(self._swigwrapper, True)    
        if resolve_cycles == True:
            setattr(self, '_resolve_cycles', True)
            DSDesignSpaceCalculateCyclicalCases(self._swigwrapper)
        
    def __del__(self):
        if self._swigwrapper is not None:
            DSDesignSpaceFree(self._swigwrapper)
            
    def __len__(self):
        return DSDesignSpaceNumberOfCases(self._swigwrapper)+1        
    
    def __getstate__(self):
        odict = self.__dict__.copy()
        odict['_swigwrapper'] = DSSWIGDSDesignSpaceEncodedBytes(self._swigwrapper)
        del odict['_independent_variables']
        return odict
    
    def __setstate__(self, state):
        self.__dict__.update(state)
        encoded = state['_swigwrapper']
        self.set_swigwrapper(DSSWIGDSDesignSpaceDecodeFromByteArray(encoded))
    
    def _case_with_signature(self, signature, constraints):
        siglist = []
        wild_cards = []
        try:
            case, subcase = signature.split('_')
            signature = case
            subcase = '_' + subcase
        except:
            subcase = ''
            pass
        i = 0
        while i < len(signature):
            if signature[i] == '(':
                start = i+1
                while signature[i] != ')':
                    i += 1
                siglist.append(int(signature[start:i]))
            elif signature[i] == '*':
                num_wild = int(self.signature[i])
                for j in xrange(num_wild):
                    new_sig = signature.replace('*', str(j+1), 1)
                    wild_cards += self._case_with_signature(new_sig, constraints)
                return wild_cards
            else:
                siglist.append(int(signature[i]))
            i+=1
        index = DSCaseNumberForSignature(siglist, DSDesignSpaceGMASystem(self._swigwrapper))
        return [self(str(index)+subcase, constraints=constraints)]
    
    def __call__(self, index_or_iterable, by_signature=False, constraints=None):
        if isinstance(index_or_iterable, (int, str)) is True:
            iterable = [index_or_iterable]
        else:
            iterable = index_or_iterable
        if by_signature is True:
            iterable = [':' + str(i) for i in iterable]
        if constraints is not None:
            if isinstance(constraints, list) is False:
                constraints = [constraints]
        cases = list()
        for index in iterable:
            if isinstance(index, int):
                index = str(index)
            if isinstance(index, str) is True:
                if index[0] == ':':
                    cases += self._case_with_signature(index[1:], constraints)
                    continue
                case_swig = DSDesignSpaceCaseWithCaseIdentifier(self._swigwrapper, index)
                if case_swig is None:
                    raise ValueError, 'Case "' + index + '" does not exits'
                name = self.name + ': Case ' + index
                case = Case(self,
                            case_swig,
                            name, 
                            constraints=constraints)
                eq=Equations(case.equations.system,
                              case.auxiliary_variables)
                cyclical_swig = DSDesignSpaceCyclicalCaseWithCaseIdentifier(self._swigwrapper, index)
                if cyclical_swig is not None:
                    cyclical = CyclicalCase(eq, cyclical_swig,
                                            name = case.name + ' (cyclical)',
                                            latex_symbols=self._latex)
                    cases.append(cyclical)
                else:
                    cases.append(case)
            else:
                raise TypeError, 'input argument must be a case identifier or case signature'
        if len(cases) == 1:
            if isinstance(index_or_iterable, str) or isinstance(index_or_iterable, int):
                cases = cases[0]
        return cases
            
    def _parse_equations(self, match_Xi=None, **kwargs):
        auxiliary_variables = self.auxiliary_variables
        if match_Xi is None:
            swigwrapper = DSSWIGDesignSpaceParseWrapper(self.equations.system,
                                                        len(self.equations),
                                                        auxiliary_variables,
                                                        len(auxiliary_variables)
                                                        )
        else:
            xi_list = match_Xi.independent_variables
            swigwrapper = DSSWIGDesignSpaceParseWrapperWithXi(self.equations.system,
                                                              len(self.equations),
                                                              auxiliary_variables,
                                                              len(auxiliary_variables),
                                                              xi_list,
                                                              len(xi_list),
                                                              )
        self.set_swigwrapper(swigwrapper)
        gma = DSDesignSpaceGMASystem(self._swigwrapper)
        eqs = DSGMASystemEquations(gma)
        equation_list = list()
        for i in xrange(0, DSGMASystemNumberOfEquations(gma)):
            expr = DSExpressionAtIndexOfExpressionArray(eqs, i)
            equation_list.append(DSExpressionAsString(expr))
            DSExpressionFree(expr)
        DSSecureFree(eqs)
        Xda = VariablePool()
        Xda.set_swigwrapper(DSVariablePoolCopy(DSGMASystemXd_a(gma)))
        equations = Equations(equation_list, auxiliary_variables=Xda.keys(), latex_symbols=self._latex)
        self._equations = equations
    
    def set_swigwrapper(self, ds_swigwrapper):
        self._swigwrapper = ds_swigwrapper
        
        Xd = VariablePool()
        Xd.set_swigwrapper(DSGMASystemXd(DSDesignSpaceGMASystem(ds_swigwrapper)))
        ## for i in VariablePool():
        ##     if i not in self.dependent_variables:
        ##         raise NameError, 'Dependent Variables are inconsistent'
        self._dependent_variables = Xd.copy()
        Xd.set_swigwrapper(None)
        Xi = VariablePool()
        Xi.set_swigwrapper(DSDesignSpaceXi(ds_swigwrapper))
        self._independent_variables = Xi.copy()
        Xi.set_swigwrapper(None)
        
    @property
    def dependent_variables(self):
        return self._dependent_variables.keys()
            
    @property
    def number_of_cases(self):
        return DSDesignSpaceNumberOfCases(self._swigwrapper)

    @property
    def signature(self):
        return DSDesignSpaceSignatureToString(self._swigwrapper)
    
    @property
    def _signature(self):
        signature_internal = DSDesignSpaceSignature(self._swigwrapper)
        signature = list()
        for i in xrange(len(self.equations)*2):
            signature.append(DSUIntegerAtIndexOfIntegerArray(signature_internal, i))
        return signature

    def _valid_cases_bounded(self, p_bounds, strict):
        lower = VariablePool(names=self.independent_variables)
        upper = VariablePool(names=self.independent_variables)
        for i in lower:
            lower[i] = 1E-20
            upper[i] = 1E20
        for (key,value) in p_bounds.iteritems():
            try:
                min_value,max_value = value
            except TypeError:
                min_value = value
                max_value = value
            if min_value > max_value:
                raise ValueError, 'parameter slice bounds are inverted: min is larger than max'
            lower[key] = min_value
            upper[key] = max_value
        if strict is True:
            valid_cases = DSDesignSpaceCalculateAllValidCasesForSlice(self._swigwrapper,
                                                                      lower._swigwrapper,
                                                                      upper._swigwrapper)
        else:
            valid_cases = DSDesignSpaceCalculateAllValidCasesForSliceNonStrict(self._swigwrapper,
                                                                               lower._swigwrapper,
                                                                               upper._swigwrapper)
        number_of_cases = DSDictionaryCount(valid_cases)
        cases = list()
        keys = [DSDictionaryKeyAtIndex(valid_cases, i) for i in xrange(0, number_of_cases)]
        for key in keys:
            case_swigwrapper = DSSWIGVoidAsCase(DSDictionaryValueForName(valid_cases, key))
            cases.append(DSCaseIdentifier(case_swigwrapper))
            DSCaseFree(case_swigwrapper)
        DSDictionaryFree(valid_cases)
        cases.sort(cmp=sort_cases)
        return cases

    def _valid_cases_expanded_bounded(self, p_bounds):
        lower = VariablePool(names=self.independent_variables)
        upper = VariablePool(names=self.independent_variables)
        for i in lower:
            lower[i] = 1E-20
            upper[i] = 1E20
        for (key,value) in p_bounds.iteritems():
            try:
                min_value,max_value = value
            except TypeError:
                min_value = value
                max_value = value
            if min_value > max_value:
                raise ValueError, 'parameter slice bounds are inverted: min is larger than max'
            lower[key] = min_value
            upper[key] = max_value
        valid_cases = DSDesignSpaceCalculateAllValidCasesForSliceByResolvingCyclicalCases(
                       self._swigwrapper,
                       lower._swigwrapper,
                       upper._swigwrapper)
        number_of_cases = DSDictionaryCount(valid_cases)
        cases = list()
        keys = [DSDictionaryKeyAtIndex(valid_cases, i) for i in xrange(0, number_of_cases)]
        for key in keys:
            case_swigwrapper = DSSWIGVoidAsCase(DSDictionaryValueForName(valid_cases, key))
            cases.append(DSCaseIdentifier(case_swigwrapper))
            DSCaseFree(case_swigwrapper)
        DSDictionaryFree(valid_cases)
        cases.sort(cmp=sort_cases)
        return cases

      
    def _valid_cases_expand_cycles(self, p_bounds):
        if p_bounds is not None:
            return self._valid_cases_expanded_bounded(p_bounds)
        valid_cases = DSDesignSpaceCalculateAllValidCasesByResolvingCyclicalCases(
                       self._swigwrapper)
        number_of_cases = DSDictionaryCount(valid_cases)
        cases = list()
        keys = [DSDictionaryKeyAtIndex(valid_cases, i) for i in xrange(0, number_of_cases)]
        for key in keys:
            case_swigwrapper = DSSWIGVoidAsCase(DSDictionaryValueForName(valid_cases, key))
            cases.append(DSCaseIdentifier(case_swigwrapper))
            DSCaseFree(case_swigwrapper)
        DSDictionaryFree(valid_cases)
        cases.sort(cmp=sort_cases)
        return cases
    
    def valid_cases(self, p_bounds=None, expand_cycles=True, strict = True):
        if self._resolve_cycles is False:
            expand_cycles = False
        if expand_cycles is True:
            return self._valid_cases_expand_cycles(p_bounds)
        if p_bounds is not None:
            return self._valid_cases_bounded(p_bounds, strict)
        all_cases = DSDesignSpaceCalculateAllValidCases(self._swigwrapper)
        number_valid = DSDesignSpaceNumberOfValidCases(self._swigwrapper)
        cases = list()
        for i in xrange(0, number_valid):
            case_swigwrapper = DSCaseAtIndexOfArray(all_cases, i)
            cases.append(DSCaseIdentifier(case_swigwrapper))
            DSCaseFree(case_swigwrapper)
        if all_cases is not None:
            DSSecureFree(all_cases)
        cases.sort(cmp=sort_cases)
        return cases
    
    def _cyclical_case_as_subcases(self, case_num, case_numbers):
        if case_num not in case_numbers:
            return case_numbers
        case = self(case_num)
        if case.is_cyclical is True:
            case_numbers.remove(case_num)
            new_case_numbers = [str(case_num) + '_' + str(j) for j in range(1, case.number_of_subcases+1)]
            case_numbers = case_numbers + new_case_numbers
            for i in new_case_numbers:
                case_numbers = self._cyclical_case_as_subcases(i, case_numbers)
        return case_numbers
    
    def cycles_to_subcases(self, case_numbers):
        original_cases = case_numbers
        case_numbers = [i for i in case_numbers]
        for i in original_cases:
            case_numbers = self._cyclical_case_as_subcases(i, case_numbers)
        return case_numbers
        
    def valid_intersecting_cases(self, intersects, case_numbers, p_bounds=None, strict=True):
        if isinstance(intersects, list) is False:
            intersects = [intersects]
        if len(case_numbers) == 0:
            return None
        intersections = list()        
        Cases = self(case_numbers)
        ## for i in xrange(len(Cases)):
        ##     case = Cases[i]
        ##     case_num = case.case_number
        ##     case_numbers = self._cyclical_case_as_subcases(case_num, case_numbers)
        valid_cases=set(range(len(case_numbers)))
        if p_bounds is not None:
            lower = VariablePool(names=self.independent_variables)
            upper = VariablePool(names=self.independent_variables)
            for key in lower:
                lower[key] = 1e-20
                upper[key] = 1e20
                for (key,value) in p_bounds.iteritems():
                    try:
                        min_value,max_value = value
                    except TypeError:
                        min_value = value
                        max_value = value
                    if min_value > max_value:
                        raise ValueError, 'parameter slice bounds are inverted: min is larger than max'
                        lower[key] = min_value
                        upper[key] = max_value
        if 1 in intersects:
            [intersections.append(i) for i in case_numbers if self(i).is_valid(p_bounds=p_bounds, strict=strict) is True]
        sets = [set([i]) for i in valid_cases]
        for i in xrange(2, max(intersects)+1):
            sets_to_check = sets
            sets = []
            identifiers = range(0, len(sets_to_check))
            comb = itertools.combinations(identifiers, 2)
            for j in comb:
                current_set = set()
                for k in j:
                    current_set = current_set.union(sets_to_check[k])
                if len(current_set) != i:
                    continue
                if current_set in sets:
                    continue
                case_int = CaseIntersection([self(case_numbers[k]) for k in current_set])                
                if case_int.is_valid(p_bounds=p_bounds) is True:
                    if i in intersects:
                        intersections.append([case_numbers[k] for k in current_set])
                    sets.append(current_set)
        return intersections
    
    def co_localize_cases(self, case_numbers, slice_parameters, 
                          constraints=None, p_bounds=None, 
                          optimize=None, minimize=True,
                          project=True,
                          by_signature=False):
        cases = self(case_numbers, by_signature=by_signature)
        to_colocalize = CaseColocalization(cases, slice_parameters, constraints=constraints)
        co_localized = to_colocalize.valid_parameter_set(p_bounds=p_bounds, 
                                                         optimize=optimize,
                                                         minimize=minimize,
                                                         project=project)
        return co_localized
        
        
    def maximum_co_localized_cases(self, case_numbers, slice_variables, p_bounds=None):
        new = False        
        if len(case_numbers) == 0:
            return None
        intersections = list()        
        Cases = self(case_numbers)
        for i in xrange(len(Cases)):
            case = Cases[i]
            case_num = case.case_number
            case_numbers = self._cyclical_case_as_subcases(case_num, case_numbers)
        valid_cases=range(len(case_numbers))
        if p_bounds is not None:
            lower = VariablePool(names=self.independent_variables)
            upper = VariablePool(names=self.independent_variables)
            for key in lower:
                lower[key] = 1e-20
                upper[key] = 1e20
                for (key,value) in p_bounds.iteritems():
                    try:
                        min_value,max_value = value
                    except TypeError:
                        min_value = value
                        max_value = value
                    if min_value > max_value:
                        raise ValueError, 'parameter slice bounds are inverted: min is larger than max'
                        lower[key] = min_value
                        upper[key] = max_value
        ## [intersections.append(i) for i in case_numbers if self(i).is_valid()is True]
        sets = [set([i]) for i in valid_cases]
        for i in xrange(2, len(case_numbers)+1):
            new = True
            sets_to_check = sets
            sets = []
            identifiers = range(0, len(sets_to_check))
            comb = itertools.combinations(identifiers, 2)
            for j in comb:
                current_set = set()
                for k in j:
                    current_set = current_set.union(sets_to_check[k])
                if len(current_set) != i:
                    continue
                if current_set in sets:
                    continue
                case_int = CaseColocalization([self(case_numbers[k]) for k in current_set], slice_variables) 
                pvals=case_int.valid_parameter_set()
                if pvals > 0:
                    if new is True:
                        intersections = []
                    new = False
                    intersections.append([case_numbers[k] for k in current_set])
                    sets.append(current_set)
        return intersections
    
    def intersecting_cases(self, intersects, case_numbers, p_bounds=None, strict=True):
         valid_ints = self.valid_intersecting_cases(intersects, case_numbers, p_bounds=p_bounds, strict=strict)
         if valid_ints is None:
             return None
         case_ints = [CaseIntersection(self(i)) for i in valid_ints]
         return case_ints
    
    def _cyclical_case(self, case, name):
        
        if isinstance(case, int) is False:
            raise TypeError, 'case must be indicated by its case number'
        sub=DSDesignSpaceCyclicalCaseWithCaseNumber(self._swigwrapper, case)
        if sub is None:
            return None
        case = Case(self, DSDesignSpaceCaseWithCaseNumber(self._swigwrapper, case), name)
        eq6=Equations(case.equations.system, case.auxiliary_variables)
        return CyclicalCase(eq6, sub, name = case.name, latex_symbols=self._latex)
    
    def line_1D_positive_roots(self, function, p_vals, slice_variable, 
                               range_slice, resolution=100):
        
        p_bounds = dict(p_vals)
        p_bounds[slice_variable] = range_slice
        valid_cases = self.valid_cases(p_bounds=p_bounds)
        lines = list()
        X_dict, Y_dict, R_dict = ({},{},{})
        unique_R = set()
        line_styles = ['-', '--', '..']
        colors = ['k', 'r', 'y']
        for case in valid_cases:
            X, Y, R = self(case).line_1D_positive_roots(function, p_vals, slice_variable,
                                                        range_slice, resolution=resolution)
            X_dict[case] = X
            Y_dict[case] = Y
            R_dict[case] = R
            unique_R.update(R)
        for i in X_dict:
            X = X_dict[i]
            Y = Y_dict[i]
            R = R_dict[i]
            for j in unique_R:
                x = list()
                y = list()
                for k in xrange(len(X)):
                    if R[k] != j:
                        if len(x):
                            lines.append((x, y, j))
                        y=list()
                        x=list()
                        continue
                    x.append(X[k])
                    y.append(Y[k])
                if len(x):
                    lines.append((x, y, j))
        return lines
                
    def data_2D_log_gain_repertoire(self, xaxis, yaxis, zaxis, p_bounds=None, cases=False):
        C=self.valid_cases(p_bounds=p_bounds)
        case_dict = {}
        behavior_set = set()
        stable = list()
        unstable = list()
        for i in C:
            case = self(i)
            key = ''
            p = case.valid_parameter_set()
            x = case.ssystem.log_gain(zaxis, xaxis)
            if x < 0:
                key = '<,'
            elif x == 0:
                key = '0,'
            else:
                key = '>,'
            y = case.ssystem.log_gain(zaxis, yaxis)
            if y < 0:
                key+= '<'
            elif y == 0:
                key += '0'
            else:
                key += '>'
            eigen = case.positive_roots(p)
            if eigen == 0:
                key += ':-'
            else:
                key += ':+'
            if key in case_dict:
                case_dict[key].append(i)
            else:
                case_dict[key] = [i]
            if (x, y, eigen) in behavior_set:
                continue
            behavior_set.add((x, y, eigen))
        if cases is True:
            return case_dict
        return behavior_set              
