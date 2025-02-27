import numpy as np
import sys
import pandas as pd
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import time
import os 
import matplotlib.pyplot as plt
import platform
#import psutil
from pyomo.environ import *

##################################################################################
############################### READING EXCEL FILE ###############################
##################################################################################

# Function to read all sheets in an Excel file and save each as a .tab file in the current directory
def read_all_sheets(excel):
    # Load the Excel file
    input_excel = pd.ExcelFile(excel)
    
    # Loop over each sheet in the workbook
    for sheet in input_excel.sheet_names:
        # Read the current sheet, skipping the first two rows
        input_sheet = pd.read_excel(excel, sheet_name=sheet, skiprows=2)

        # Drop only fully empty rows (optional)
        data_nonempty = input_sheet.dropna(how='all')

        # Replace spaces in column names with underscores
        data_nonempty.columns = data_nonempty.columns.astype(str).str.replace(' ', '_')

        # Fill missing values with an empty string
        data_nonempty = data_nonempty.fillna('')

        # Convert all columns to strings before replacing whitespace characters in values
        data_nonempty = data_nonempty.applymap(lambda x: str(x) if pd.notnull(x) else "")
        
        # Save as a .tab file using only the sheet name as the file namec
        output_filename = f"{sheet}.tab"
        data_nonempty.to_csv(output_filename, header=True, index=False, sep='\t')
        print(f"Saved file: {output_filename}")

# Call the function with your Excel file
read_all_sheets('Test_data.xlsx')

####################################################################
######################### MODEL SPECIFICATIONS #####################
####################################################################

model = pyo.AbstractModel()
data = pyo.DataPortal() #Loading the data from a data soruce in a uniform manner (Excel)


"""
SETS 
"""
#Declaring Sets
model.Time = pyo.Set(ordered=True) #Set of time periods (hours)
model.LoadShiftingIntervals = pyo.Set(ordered=True)
model.TimeLoadShift = pyo.Set(dimen = 2, ordered = True) #Subset of time periods for load shifting
model.Month = pyo.Set(ordered = True) #Set of months
model.TimeInMonth = pyo.Set(within = model.Time) #Subset of time periods in month m
model.Technology = pyo.Set(ordered = True) #Set of technologies
model.EnergyCarrier = pyo.Set(ordered = True)
model.TechnologyToEnergyCarrier = pyo.Set(dimen=3, ordered = True)
model.EnergyCarrierToTechnology = pyo.Set(dimen=3, ordered = True)
model.FlexibleLoad = pyo.Set(ordered=True) #Set of flexible loads (batteries)
model.FlexibleLoadForEnergyCarrier = pyo.Set(dimen = 2, ordered = True)
model.ShiftableLoadForEnergyCarrier = pyo.Set(dimen = 2, ordered = True, within = model.FlexibleLoadForEnergyCarrier)
model.Nodes = pyo.Set(ordered=True) #Set of Nodess
model.Nodes_DA = pyo.Set(within = model.Nodes) #SubSet of Nodess
model.Nodes_RT = pyo.Set(within = model.Nodes) #SubSet of Nodess
model.Parent_Node = pyo.Set(dimen = 2, ordered = True)
model.Mode_of_operation = pyo.Set(ordered = True)

#Reading the Sets, and loading the data
data.load(filename="Set_of_TimeSteps.tab", format="set", set=model.Time)
data.load(filename="Subset_LoadShiftWindow.tab", format="set", set=model.TimeLoadShift)
data.load(filename="Set_of_Month.tab", format = "set", set=model.Month)
data.load(filename="Subset_of_TimeStepsInMonth.tab", format = "set", set=model.TimeInMonth)
data.load(filename="Set_of_Technology.tab", format = "set", set=model.Technology)
data.load(filename="Set_of_FlexibleLoad.tab", format="set", set=model.FlexibleLoad)
data.load(filename="Set_of_Nodes.tab", format="set", set=model.Nodes)
data.load(filename="Set_of_EnergyCarrier.tab", format="set", set=model.EnergyCarrier)
data.load(filename="Subset_TechToEC.tab", format="set", set=model.TechnologyToEnergyCarrier)
data.load(filename="Subset_ECToTech.tab", format="set", set=model.EnergyCarrierToTechnology)
data.load(filename="Set_of_FlexibleLoadForEC.tab", format="set", set=model.FlexibleLoadForEnergyCarrier)
data.load(filename="Subset_ShiftableLoadForEC.tab", format="set", set=model.ShiftableLoadForEnergyCarrier)
data.load(filename="Set_of_LoadShiftingInterval.tab", format = "set", set = model.LoadShiftingIntervals)
data.load(filename="Subset_Plan_Nodes.tab", format = "set", set = model.Nodes_DA)
data.load(filename="Subset_RT_Nodes.tab", format = "set", set = model.Nodes_RT)
data.load(filename="Set_parent_coupling.tab", format = "set", set = model.Parent_Node)
data.load(filename="Set_Mode_of_Operation.tab", format = "set", set = model.Mode_of_operation)


"""
PARAMETERS
"""
#Declaring Parameters
model.Cost_Energy = pyo.Param(model.Nodes, model.Time, model.Technology, default=0.0)  # Cost of using energy source i at time t
model.Cost_Battery = pyo.Param(model.FlexibleLoad)
model.Cost_Export = pyo.Param(model.Nodes, model.Time, model.EnergyCarrier)  # Income from exporting energy to the grid at time t
model.Cost_Expansion_Tec = pyo.Param(model.Technology) #Capacity expansion cost
model.Cost_Expansion_Bat = pyo.Param(model.FlexibleLoad) #Capacity expansion cost
model.Cost_Emission = pyo.Param() #Carbon price
model.Cost_Grid = pyo.Param() #Grid tariff
model.Cost_Imbal = pyo.Param()
model.aFRR_Up_Capacity_Price = pyo.Param(model.Nodes, model.Time, default=0.0)  # Capacity Price for aFRR up regulation 
model.aFRR_Dwn_Capacity_Price = pyo.Param(model.Nodes, model.Time, default=0.0)  # Capcaity Price for aFRR down regulation
model.aFRR_Up_Activation_Price = pyo.Param(model.Nodes, model.Time, default=0.0)  # Activation Price for aFRR up regulation 
model.aFRR_Dwn_Activation_Price = pyo.Param(model.Nodes, model.Time, default=0.0)  # Activatioin Price for aFRR down regulation 
model.Spot_Price = pyo.Param(model.Nodes, model.Time, default=0.0)
model.Intraday_Price = pyo.Param(model.Nodes, model.Time, default=0.0)
#model.RK_Up_Price = pyo.Param(model.Nodes, model.Time, default=0.0)
#model.RK_Dwn_Price = pyo.Param(model.Nodes, model.Time, default=0.0)
model.Demand = pyo.Param(model.Nodes, model.Time, model.EnergyCarrier, default = 0)  # Energy demand 
model.Max_charge_discharge_rate = pyo.Param(model.FlexibleLoad, default = 1) # Maximum symmetric charge and discharge rate
model.Charge_Efficiency = pyo.Param(model.FlexibleLoad)  # Efficiency of charging flexible load b [-]
model.Discharge_Efficiency = pyo.Param(model.FlexibleLoad)  # Efficiency of discharging flexible load b [-]
model.Technology_To_EnergyCarrier_Efficiency = pyo.Param(model.TechnologyToEnergyCarrier) #Efficiency of technology i when supplying fuel e
model.EnergyCarrier_To_Technlogy_Efficiency = pyo.Param(model.EnergyCarrierToTechnology) #Efficiency of technology i when consuming fuel e
model.Max_Storage_Capacity = pyo.Param(model.FlexibleLoad)  # Maximum energy storage capacity of flexible load b [MWh]
model.Self_Discharge = pyo.Param(model.FlexibleLoad)  # Self-discharge rate of flexible load b [%]
model.Initial_SOC = pyo.Param(model.FlexibleLoad)  # Initial state of charge for flexible load b [-]
model.Node_Probability = pyo.Param(model.Nodes)  # Probability of Nodes s [-]
model.Max_Cable_Capacity = pyo.Param()  # Maximum capacity of power cable for import/export [MW]
model.Up_Shift_Max = pyo.Param()  # Maximum allowable up-shifting in load shifting periods as a percentage of demand [% of demand]
model.Down_Shift_Max = pyo.Param()  # Maximum allowable down-shifting in load shifting periods as a percentage of demand [% of demand]
model.Initial_Installed_Capacity = pyo.Param(model.Technology) #Initial installed capacity at site for technology i
model.Ramping_Factor = pyo.Param(model.Technology)
model.Availability_Factor = pyo.Param(model.Nodes, model.Time, model.Technology) #Availability factor for technology delivering to energy carrier 
model.Carbon_Intensity = pyo.Param(model.Technology, model.Mode_of_operation) #Carbon intensity when using technology i in mode o
model.Max_Export = pyo.Param() #Maximum allowable export per year, if no concession is given
model.Activation_Factor_UP_Regulation = pyo.Param(model.Nodes, model.Time, default = 0) # Activation factor determining the duration of up regulation
model.Activation_Factor_DWN_Regulation = pyo.Param(model.Nodes, model.Time, default = 0) # Activation factor determining the duration of dwn regulation
model.Activation_Factor_ID_Up = pyo.Param(model.Nodes, model.Time, default = 0) # Activation factor determining the duration of up regulation
model.Activation_Factor_ID_Dwn = pyo.Param(model.Nodes, model.Time, default = 0) # Activation factor determining the duration of dwn regulation
model.Available_Excess_Heat = pyo.Param() #Fraction of the total available excess heat at usable temperature level to \\& be used an energy source for the heat pump.
model.Energy2Power_Ratio = pyo.Param(model.FlexibleLoad)
model.Max_CAPEX_tech = pyo.Param(model.Technology)
model.Max_CAPEX_flex = pyo.Param(model.FlexibleLoad)
model.Max_Carbon_Emission = pyo.Param() #Maximum allowable carbon emissions per year

#Reading the Parameters, and loading the data
data.load(filename="Par_EnergyCost.tab", param=model.Cost_Energy, format = "table")
data.load(filename="Par_BatteryCost.tab", param=model.Cost_Battery, format = "table")
data.load(filename="Par_ExportCost.tab", param=model.Cost_Export, format = "table")
data.load(filename="Par_CostExpansion_Tec.tab", param=model.Cost_Expansion_Tec, format = "table")
data.load(filename="Par_CostExpansion_Bat.tab", param=model.Cost_Expansion_Bat, format = "table")
data.load(filename="Par_CostEmission.tab", param=model.Cost_Emission, format = "table")
data.load(filename="Par_CostGridTariff.tab", param=model.Cost_Grid, format = "table")
data.load(filename="Par_CostImbalance.tab", param=model.Cost_Imbal, format = "table")
data.load(filename="Par_aFRR_UP_CAP_price.tab", param=model.aFRR_Up_Capacity_Price, format = "table")
data.load(filename="Par_aFRR_DWN_CAP_price.tab", param=model.aFRR_Dwn_Capacity_Price, format = "table")
data.load(filename="Par_aFRR_UP_ACT_price.tab", param=model.aFRR_Up_Activation_Price, format = "table")
data.load(filename="Par_aFRR_DWN_ACT_price.tab", param=model.aFRR_Dwn_Activation_Price, format = "table")
data.load(filename="Par_SpotPrice.tab", param=model.Spot_Price, format = "table")
data.load(filename="Par_IntradayPrice.tab", param=model.Intraday_Price, format = "table")
#data.load(filename="Par_RK_UpPrice.tab", param=model.RK_Up_Price, format = "table")
#data.load(filename="Par_RK_DwnPrice.tab", param=model.RK_Dwn_Price, format = "table")
data.load(filename="Par_EnergyDemand.tab", param=model.Demand, format = "table")
data.load(filename="Par_MaxChargeDischargeRate.tab", param=model.Max_charge_discharge_rate, format = "table")
data.load(filename="Par_ChargeEfficiency.tab", param=model.Charge_Efficiency, format = "table")
data.load(filename="Par_DischargeEfficiency.tab", param=model.Discharge_Efficiency, format = "table")
data.load(filename="Par_TechToEC_Efficiency.tab", param=model.Technology_To_EnergyCarrier_Efficiency, format = "table")
data.load(filename="Par_ECToTech_Efficiency.tab", param=model.EnergyCarrier_To_Technlogy_Efficiency, format = "table")
data.load(filename="Par_MaxStorageCapacity.tab", param=model.Max_Storage_Capacity, format = "table")
data.load(filename="Par_SelfDischarge.tab", param=model.Self_Discharge, format = "table")
data.load(filename="Par_InitialSoC.tab", param=model.Initial_SOC, format = "table")
data.load(filename="Par_NodesProbability.tab", param=model.Node_Probability, format = "table")
data.load(filename="Par_MaxCableCapacity.tab", param=model.Max_Cable_Capacity, format = "table")
data.load(filename="Par_MaxUpShift.tab", param=model.Up_Shift_Max, format = "table")
data.load(filename="Par_MaxDwnShift.tab", param=model.Down_Shift_Max, format = "table")
data.load(filename="Par_InitialCapacityInstalled.tab", param=model.Initial_Installed_Capacity, format = "table")
data.load(filename="Par_AvailabilityFactor.tab", param=model.Availability_Factor, format = "table")
data.load(filename="Par_CarbonIntensity.tab", param=model.Carbon_Intensity, format = "table")
data.load(filename="Par_MaxExport.tab", param=model.Max_Export, format = "table")
data.load(filename="Par_ActivationFactor_Up_Reg.tab", param=model.Activation_Factor_UP_Regulation, format = "table")
data.load(filename="Par_ActivationFactor_Dwn_Reg.tab", param=model.Activation_Factor_DWN_Regulation, format = "table")
data.load(filename="Par_ActivationFactor_ID_Up_Reg.tab", param=model.Activation_Factor_ID_Up, format = "table")
data.load(filename="Par_ActivationFactor_ID_Dwn_Reg.tab", param=model.Activation_Factor_ID_Dwn, format = "table")
data.load(filename="Par_AvailableExcessHeat.tab", param=model.Available_Excess_Heat, format = "table")
data.load(filename="Par_Energy2Power_ratio.tab", param=model.Energy2Power_Ratio, format = "table")
data.load(filename="Par_Ramping_factor.tab", param=model.Ramping_Factor, format = "table")
data.load(filename="Par_Max_CAPEX_tec.tab", param=model.Max_CAPEX_tech, format = "table")
data.load(filename="Par_Max_CAPEX_bat.tab", param=model.Max_CAPEX_flex, format = "table")
data.load(filename="Par_Max_Carbon_Emission.tab", param=model.Max_Carbon_Emission, format = "table")


"""
VARIABLES
"""
#Declaring Variables
model.x_UP = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
model.x_DWN = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
#model.x_UP_Tot = pyo.Var(model.Nodes, model.Time, domain=pyo.NonNegativeReals)
#model.x_DWN_Tot = pyo.Var(model.Nodes, model.Time, domain=pyo.NonNegativeReals)
model.x_DA_Up = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
model.x_DA_Dwn = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
model.x_ID_Up = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
model.x_ID_Dwn = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
#model.x_RT_Up = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
#model.x_RT_Dwn = pyo.Var(model.Nodes, model.Time, domain= pyo.NonNegativeReals)
model.y_out = pyo.Var(model.Nodes, model.Time, model.TechnologyToEnergyCarrier, domain = pyo.NonNegativeReals)
model.y_in = pyo.Var(model.Nodes, model.Time, model.EnergyCarrierToTechnology, domain = pyo.NonNegativeReals)
model.y_activity = pyo.Var(model.Nodes, model.Time, model.Technology, model.Mode_of_operation, domain = pyo.NonNegativeReals)
#model.z_export = pyo.Var(model.Nodes, model.Time, model.EnergyCarrier, domain = pyo.NonNegativeReals, bounds = (0, 0))
model.q_charge = pyo.Var(model.Nodes, model.Time, model.FlexibleLoad, domain= pyo.NonNegativeReals)
model.q_discharge = pyo.Var(model.Nodes, model.Time, model.FlexibleLoad, domain= pyo.NonNegativeReals)
model.q_SoC = pyo.Var(model.Nodes, model.Time, model.FlexibleLoad, domain= pyo.NonNegativeReals)
model.v_new_tech = pyo.Var(model.Technology, domain = pyo.NonNegativeReals, bounds = (0, 0)) 
model.v_new_bat = pyo.Var(model.FlexibleLoad, domain = pyo.NonNegativeReals, bounds = (0, 0))
model.y_max = pyo.Var(model.Nodes, model.Month, domain = pyo.NonNegativeReals)
#model.d_flex = pyo.Var(model.Nodes, model.Time, model.EnergyCarrier, domain = pyo.NonNegativeReals)
model.I_inv = pyo.Var(domain = pyo.NonNegativeReals)
model.I_cap_bid = pyo.Var(model.Time, domain = pyo.NonNegativeReals)
model.I_activation = pyo.Var(model.Nodes, model.Time, domain = pyo.NonNegativeReals)
model.I_DA = pyo.Var(model.Nodes, model.Time, domain = pyo.NonNegativeReals)
model.I_ID = pyo.Var(model.Nodes, model.Time, domain = pyo.NonNegativeReals)
model.I_OPEX = pyo.Var(model.Nodes, model.Time, domain = pyo.NonNegativeReals)

"""
OBJECTIVE
""" 
"""
def objective(model):
    obj_expr = sum(
        model.Cost_Expansion_Tec[i] * model.v_new_tech[i] for i in model.Technology
    ) + sum(
        model.Cost_Expansion_Bat[b] * model.v_new_bat[b] for b in model.FlexibleLoad
    ) + sum(
        sum(model.Node_Probability[n] * (
            - (model.aFRR_Up_Capacity_Price[n, t] * model.x_UP[n, t] +
               model.aFRR_Dwn_Capacity_Price[n, t] * model.x_DWN[n, t])
        ) for n in model.Nodes_DA)

        + sum(model.Node_Probability[n] * (
            - model.Activation_Factor_UP_Regulation[n, t] * model.aFRR_Up_Activation_Price[n, t] * model.x_UP[n, t]
            + model.Activation_Factor_DWN_Regulation[n, t] * model.aFRR_Dwn_Activation_Price[n, t] * model.x_DWN[n, t]
            
            + model.Spot_Price[n, t] * (model.x_DA_Up[n, t] - model.x_DA_Dwn[n, t])
            + model.Intraday_Price[n, t] * (
                model.Activation_Factor_ID_Up[n, t] * model.x_ID_Up[n, t] 
                - model.Activation_Factor_ID_Dwn[n, t] * model.x_ID_Dwn[n, t]
            )

            + sum(
                model.y_activity[n, t, i, o] * (model.Cost_Energy[n, t, i] 
                + model.Carbon_Intensity[i, o] * model.Cost_Emission)
                for (i, e, o) in model.TechnologyToEnergyCarrier #MÅ OGSÅ LEGGE TIL FOR Y_IN HVIS DET SKAL VÆRE EXPORT
            ) 

            + sum(model.Cost_Grid * model.y_max[n, m] for m in model.Month)

            + sum(model.Cost_Battery[b] * model.q_discharge[n, t, b] for b in model.FlexibleLoad)
        ) for n in model.Nodes_RT)
    for t in model.Time
    )

    return obj_expr  # Return the fully evaluated expression

model.Objective = pyo.Objective(rule=objective, sense=pyo.minimize)
"""

#OBJECTIVE SHORT FORM
def objective(model):
    obj_expr = model.I_inv + sum(model.I_cap_bid[t] + sum(model.Node_Probability[n] * (model.I_activation[n, t] + model.I_DA[n, t] + model.I_ID[n, t] + model.I_OPEX[n, t]) for n in model.Nodes_RT) for t in model.Time)

    return obj_expr  # Return the fully evaluated expression

model.Objective = pyo.Objective(rule=objective, sense=pyo.minimize)



"""
CONSTRAINTS
"""  

###########################################
############## COST BALANCES ##############
###########################################
def cost_investment(model):
    return model.I_inv == (sum(
        model.Cost_Expansion_Tec[i] * model.v_new_tech[i] for i in model.Technology
    ) + sum(
        model.Cost_Expansion_Bat[b] * model.v_new_bat[b] for b in model.FlexibleLoad
    ))
model.InvestmentCost = pyo.Constraint(rule=cost_investment)

def cost_capacity_bid(model, t):
    return model.I_cap_bid[t] == sum(model.Node_Probability[n] * (
            - (model.aFRR_Up_Capacity_Price[n, t] * model.x_UP[n, t] +
               model.aFRR_Dwn_Capacity_Price[n, t] * model.x_DWN[n, t])
        ) for n in model.Nodes_DA)
model.CapacityBidCost = pyo.Constraint(model.Time, rule=cost_capacity_bid)

def cost_activation(model, n, p, t):
    if n in model.Nodes_RT:
        return model.I_activation[n, t] == (- model.Activation_Factor_UP_Regulation[n, t] * model.aFRR_Up_Activation_Price[n, t] * model.x_UP[p, t]
                + model.Activation_Factor_DWN_Regulation[n, t] * model.aFRR_Dwn_Activation_Price[n, t] * model.x_DWN[p, t])
    else:
        return pyo.Constraint.Skip
model.ActivationCost = pyo.Constraint(model.Parent_Node, model.Time, rule=cost_activation)

def cost_DA(model, n, p, t):
    if n in model.Nodes_RT:
        return model.I_DA[n, t] == model.Spot_Price[n, t] * (model.x_DA_Up[p, t] - model.x_DA_Dwn[p, t])
    else:
        return pyo.Constraint.Skip
model.DACost = pyo.Constraint(model.Parent_Node, model.Time, rule=cost_DA) 

def cost_ID(model, n, p, t):
    if n in model.Nodes_RT:
        return model.I_ID[n, t] == model.Intraday_Price[n, t] * (
                model.Activation_Factor_ID_Up[n, t] * model.x_ID_Up[p, t] 
                - model.Activation_Factor_ID_Dwn[n, t] * model.x_ID_Dwn[p, t]
            )
    else:
        return pyo.Constraint.Skip
model.IDCost = pyo.Constraint(model.Parent_Node, model.Time, rule=cost_ID)    

def cost_opex(model, n, t):
    return model.I_OPEX[n, t] == (sum(
                model.y_activity[n, t, i, o] * (model.Cost_Energy[n, t, i] 
                + model.Carbon_Intensity[i, o] * model.Cost_Emission)
                for (i, e, o) in model.TechnologyToEnergyCarrier #MÅ OGSÅ LEGGE TIL FOR Y_IN HVIS DET SKAL VÆRE EXPORT
            ) 

            + sum(model.Cost_Grid * model.y_max[n, m] for m in model.Month)

            + sum(model.Cost_Battery[b] * model.q_discharge[n, t, b] for b in model.FlexibleLoad)
    )
model.OPEXCost = pyo.Constraint(model.Nodes_RT, model.Time, rule=cost_opex)


###########################################
############## ENERGY BALANCE #############
###########################################

def energy_balance(model, n, t, e):
    return (
        model.Demand[n, t, e]
        == sum(sum(model.y_out[n, t, i, e, o] for i in model.Technology if (i,e,o) in model.TechnologyToEnergyCarrier)
        - sum(model.y_in[n, t, i, e, o] for i in model.Technology if(i,e,o) in model.EnergyCarrierToTechnology) for o in model.Mode_of_operation)
        - sum(
            model.Charge_Efficiency[b] * model.q_charge[n, t, b] - model.q_discharge[n, t, b]
            for b in model.FlexibleLoad if (b,e) in model.FlexibleLoadForEnergyCarrier
        )
    )
model.EnergyBalance = pyo.Constraint(model.Nodes_RT, model.Time, model.EnergyCarrier, rule=energy_balance)

#####################################################################################
########################### MARKET BALANCE DA/ID/RT #################################
#####################################################################################
 
def market_balance_import_plan(model, n, t, i, e, o):
    if (i, e, o) == ("Power_Grid", "Electricity", 1):
        return (model.y_out[n, t, i, e, o] == model.x_DA_Up[n, t] + model.x_ID_Up[n, t] + model.x_DWN[n, t])
    else:
        return pyo.Constraint.Skip      
model.MarketBalanceImportPlan = pyo.Constraint(model.Nodes_DA, model.Time, model.TechnologyToEnergyCarrier, rule = market_balance_import_plan)

def market_balance_export_plan(model, n, t, i, e, o):
    if (i, e, o) == ("Power_Grid", "Electricity", 2):
        return (model.y_in[n, t, i, e, o] == model.x_DA_Dwn[n, t] + model.x_ID_Dwn[n, t] + model.x_UP[n, t])
    else:
        return pyo.Constraint.Skip      
model.MarketBalanceExportPlan = pyo.Constraint(model.Nodes_DA, model.Time, model.EnergyCarrierToTechnology, rule = market_balance_export_plan)

def market_balance_import_RT(model, n, p, t, i, e, o):
    if (i, e, o) == ("Power_Grid", "Electricity", 1) and n in model.Nodes_RT:
        return (model.y_out[n, t, i, e, o] == model.x_DA_Up[p, t] + model.Activation_Factor_ID_Up[n,t]*model.x_ID_Up[p, t] + model.Activation_Factor_DWN_Regulation[n, t] * model.x_DWN[p, t])
    else:
        return pyo.Constraint.Skip      
model.MarketBalanceImportRT = pyo.Constraint(model.Parent_Node, model.Time, model.TechnologyToEnergyCarrier, rule = market_balance_import_RT)

def market_balance_export_RT(model, n, p, t, i, e, o):
    if (i, e, o) == ("Power_Grid", "Electricity", 2) and n in model.Nodes_RT:
        return (model.y_in[n, t, i, e, o] == model.x_DA_Dwn[p, t] + model.Activation_Factor_ID_Dwn[n,t]*model.x_ID_Dwn[p, t] + model.Activation_Factor_UP_Regulation[n, t] * model.x_UP[p, t])
    else:
        return pyo.Constraint.Skip      
model.MarketBalanceExportRT = pyo.Constraint(model.Parent_Node, model.Time, model.EnergyCarrierToTechnology, rule = market_balance_export_RT)


def Max_ID_Adjustment(model, n, t):
        return (model.x_ID_Up[n, t] + model.x_ID_Dwn[n, t] <= 10)
model.MaxIDAdjustment = pyo.Constraint(model.Nodes_DA, model.Time, rule = Max_ID_Adjustment)


#####################################################################################
########################### CONVERSION BALANCE ######################################
#####################################################################################

def conversion_balance_out(model, n, t, i, e, o):
        return (model.y_out[n, t, i, e, o] == model.y_activity[n, t, i, o] * model.Technology_To_EnergyCarrier_Efficiency[i, e, o])     
model.ConversionBalanceOut = pyo.Constraint(model.Nodes_RT, model.Time, model.TechnologyToEnergyCarrier, rule = conversion_balance_out)

def conversion_balance_in(model, n, t, i, e, o):
        return (model.y_in[n, t, i, e, o] == model.y_activity[n, t, i, o] * model.EnergyCarrier_To_Technlogy_Efficiency[i, e, o])           
model.ConversionBalanceIn = pyo.Constraint(model.Nodes_RT, model.Time, model.EnergyCarrierToTechnology, rule = conversion_balance_in)

#####################################################################################
########################### TECHNOLOGY RAMPING CONSTRAINTS ##########################
#####################################################################################

def Ramping_Technology(model, n, t, i, e, o):
        if t > 1:
            return (model.y_out[n, t, i, e, o] - model.y_out[n, t-1, i, e, o] <= model.Ramping_Factor[i] * (model.Initial_Installed_Capacity[i] + model.v_new_tech[i]))
        else:
            return (model.y_out[n, t, i, e, o] <= model.Ramping_Factor[i] * (model.Initial_Installed_Capacity[i] + model.v_new_tech[i]))        
model.RampingTechnology = pyo.Constraint(model.Nodes_RT, model.Time, model.TechnologyToEnergyCarrier, rule = Ramping_Technology)

#####################################################################################
############## HEAT PUMP LIMITATION - MÅ ENDRES I HENHOLD TIL INPUTDATA #############
#####################################################################################

def heat_pump_input_limitation_LT(model, n, t):
    return (
        model.y_out[n, t, 'HeatPump_LT', 'LT', 1] - model.y_in[n, t, 'HeatPump_LT', 'Electricity', 1]
        <= model.Available_Excess_Heat * (model.Demand[n, t, 'LT'])# + model.Demand[s, t, 'HT'])
    )
model.HeatPumpInputLimitationLT = pyo.Constraint(model.Nodes_RT, model.Time, rule=heat_pump_input_limitation_LT)

def heat_pump_input_limitation_MT(model, n, t):
    return (
        model.y_out[n, t, 'HeatPump_MT', 'MT', 1] - model.y_in[n, t, 'HeatPump_MT', 'Electricity', 1]
        <= model.Available_Excess_Heat * (model.Demand[n, t, 'MT'])# + model.Demand[s, t, 'HT'])
    )
model.HeatPumpInputLimitationMT = pyo.Constraint(model.Nodes_RT, model.Time, rule=heat_pump_input_limitation_MT)

######################################################
############## LOAD SHIFTING CONSTRAINTS #############
######################################################

def loads_shifting_time_window(model, n, i, b, e):
        return sum(model.q_charge[n,t,b] - model.q_discharge[n,t,b]/model.Discharge_Efficiency[b] for (interval, t) in model.TimeLoadShift if interval == i) == 0
model.LoadShiftingWindow = pyo.Constraint(model.Nodes_RT, model.LoadShiftingIntervals, model.ShiftableLoadForEnergyCarrier, rule=loads_shifting_time_window)

def no_discharge_outside_load_shift(model, n, t, b, e):
    if not any(t == load_t[1] for load_t in model.TimeLoadShift):
        return model.q_discharge[n, t, b]  == 0
    else:
        return pyo.Constraint.Skip
model.NoDischargeOutsideLoadShift = pyo.Constraint(model.Nodes_RT, model.Time, model.ShiftableLoadForEnergyCarrier, rule=no_discharge_outside_load_shift)

def no_charge_outside_load_shift(model, n, t, b, e):
    if not any(t == load_t[1] for load_t in model.TimeLoadShift):
        return model.q_charge[n, t, b]  == 0
    else:
        return pyo.Constraint.Skip
model.NochargeOutsideLoadShift = pyo.Constraint(model.Nodes_RT, model.Time, model.ShiftableLoadForEnergyCarrier, rule=no_charge_outside_load_shift)

###########################################################
############## MAX ALLOWABLE UP/DOWN SHIFT ################
###########################################################

def Max_total_up_dwn_load_shift(model, n, i, t, b, e):
    #if e == 'Electricity':
        # Extract all time steps `tt` for the given interval `i`
    relevant_times = [tt for (j, tt) in model.TimeLoadShift if j == i]        
    if t in relevant_times:
        return model.q_charge[n,t,b] + model.q_discharge[n,t,b]/model.Discharge_Efficiency[b] <= model.Up_Shift_Max * model.Demand[n,t,e]        
    return pyo.Constraint.Skip
model.MaxTotalUpDwnLoadShift = pyo.Constraint(model.Nodes, model.TimeLoadShift, model.ShiftableLoadForEnergyCarrier, rule=Max_total_up_dwn_load_shift)



########################################################################
############## FLEXIBLE ASSET CONSTRAINTS/STORAGE DYNAMICS #############
########################################################################

def flexible_asset_charge_discharge_limit(model, n, t, b, e):
    if (b,e) not in model.ShiftableLoadForEnergyCarrier:
        return (
            model.q_charge[n, t, b] 
            + model.q_discharge[n, t, b] / model.Discharge_Efficiency[b] 
            <= model.Max_charge_discharge_rate[b] + model.Energy2Power_Ratio[b] * model.v_new_bat[b]
        )
    else:
        return pyo.Constraint.Skip
model.FlexibleAssetChargeDischargeLimit = pyo.Constraint(model.Nodes_RT, model.Time, model.FlexibleLoadForEnergyCarrier, rule=flexible_asset_charge_discharge_limit)

def state_of_charge(model, n, t, b, e):
    if t == 1:  # Initialisation of flexible assets
        return (
            model.q_SoC[n, t, b]
            == model.Initial_SOC[b] * (model.Max_Storage_Capacity[b] + model.v_new_bat[b]) * (1 - model.Self_Discharge[b])
            + model.q_charge[n, t, b]
            - model.q_discharge[n, t, b] / model.Discharge_Efficiency[b]
        )
    else:       # Storage Dynamics
        return (
            model.q_SoC[n, t, b]
            == model.q_SoC[n, t-1, b] * (1 - model.Self_Discharge[b])
            + model.q_charge[n, t, b]
            - model.q_discharge[n, t, b] / model.Discharge_Efficiency[b]
        )
model.StateOfCharge = pyo.Constraint(model.Nodes_RT, model.Time, model.FlexibleLoadForEnergyCarrier, rule=state_of_charge)

def end_of_horizon_SoC(model, n, t, b, e):
    if t == model.Time.last():
        return model.q_SoC[n, t, b] == model.Initial_SOC[b] * (model.Max_Storage_Capacity[b] + model.v_new_bat[b])
    else:
        return pyo.Constraint.Skip
model.EndOfHorizonSoC = pyo.Constraint(model.Nodes_RT, model.Time, model.FlexibleLoadForEnergyCarrier, rule = end_of_horizon_SoC)


def flexible_asset_energy_limit(model, n, t, b, e):
    return model.q_SoC[n, t, b] <= model.Max_Storage_Capacity[b] + model.v_new_bat[b]
model.FlexibleAssetEnergyLimits = pyo.Constraint(model.Nodes_RT, model.Time, model.FlexibleLoadForEnergyCarrier, rule=flexible_asset_energy_limit)

####################################################
############## AVAILABILITY CONSTRAINT #############
####################################################

def supply_limitation(model, n, t, i, e, o):
    return (sum(model.y_out[n, t, i, e, o] for e,o in model.EnergyCarrier * model.Mode_of_operation if (i,e,o) in model.TechnologyToEnergyCarrier)  
            <= model.Availability_Factor[n, t, i] * (model.Initial_Installed_Capacity[i] + model.v_new_tech[i]))
model.SupplyLimitation = pyo.Constraint(model.Nodes_RT, model.Time, model.TechnologyToEnergyCarrier, rule=supply_limitation)

##############################################################
############## EXPORT LIMITATION AND GRID TARIFF #############
##############################################################

def export_limitation(model, n, t, i, e, o):
    if (i, e, o) == ('Power_grid', 'Electricity', 2):
        return model.y_in[n, t, i, e, o] <= model.Max_Export
    else:
        return pyo.Constraint.Skip
model.ExportLimitation = pyo.Constraint(model.Nodes_RT, model.Time, model.EnergyCarrierToTechnology, rule=export_limitation)

def peak_load(model, n, t, i, e, o, m):
    if i == 'Power_Grid' and e == 'Electricity':
        return (model.y_out[n, t, i, e, o] <= model.y_max[n, m])
    else:
        return pyo.Constraint.Skip
model.PeakLoad = pyo.Constraint(model.Nodes_RT, model.TimeInMonth, model.TechnologyToEnergyCarrier, model.Month, rule=peak_load)

##############################################################
##################### INVESTMENT LIMITATIONS #################
##############################################################

def CAPEX_technology_limitations(model, i):
    return (model.Cost_Expansion_Tec[i] * model.v_new_tech[i] <= model.Max_CAPEX_tech[i])
model.CAPEXTechnologyLim = pyo.Constraint(model.Technology, rule=CAPEX_technology_limitations)

def CAPEX_flexibleLoad_limitations(model, b):
    return (model.Cost_Expansion_Bat[b] * model.v_new_bat[b] <= model.Max_CAPEX_flex[b])
model.CAPEXFlexibleLoadLim = pyo.Constraint(model.FlexibleLoad, rule=CAPEX_flexibleLoad_limitations)

##############################################################
##################### CARBON EMISSION LIMIT ##################
##############################################################

def Carbon_Emission_Limit(model, n):
    total_emission = sum(
        model.y_activity[n, t, i, o] * model.Carbon_Intensity[i, o]
        for t in model.Time
        for (i,e,o) in model.TechnologyToEnergyCarrier
    )
    return total_emission <= model.Max_Carbon_Emission
model.CarbonEmissionLimit = pyo.Constraint(model.Nodes_RT, rule=Carbon_Emission_Limit)


##############################################################
##################### NON-ANTICIPATIVITY #####################
##############################################################

def Day_ahead_NA_up(model, n, p, t):
    return (model.x_DA_Up[n, t] == model.x_DA_Up[p, t])
model.DayAheadToIntradayUp = pyo.Constraint(model.Parent_Node, model.Time, rule=Day_ahead_NA_up)

def Day_ahead_NA_dwn(model, n, p, t):
    return (model.x_DA_Dwn[n, t] == model.x_DA_Dwn[p, t])
model.DayAheadToIntradayDwn = pyo.Constraint(model.Parent_Node, model.Time, rule=Day_ahead_NA_dwn)

def Intraday_Up_NA(model, n, p, t):
    return (model.x_ID_Up[n, t] == model.x_ID_Up[p, t])
    
model.IntradayToRealTimeUp = pyo.Constraint(model.Parent_Node, model.Time, rule=Intraday_Up_NA)

def Intraday_Dwn_NA(model, n, p, t):
    return (model.x_ID_Dwn[n, t] == model.x_ID_Dwn[p, t])
    
model.IntradayToRealTimeDown = pyo.Constraint(model.Parent_Node, model.Time, rule=Intraday_Dwn_NA)

def Reserve_Capacity_Dwn_NA(model, n, p, t):
    return (model.x_DWN[n, t] == model.x_DWN[p, t])
    
model.ReserveCapacityDwn = pyo.Constraint(model.Parent_Node, model.Time, rule = Reserve_Capacity_Dwn_NA) 

def Reserve_Capacity_Up_NA(model, n, p, t):
    return (model.x_UP[n, t] == model.x_UP[p, t])
    
model.ReserveCapacityUp = pyo.Constraint(model.Parent_Node, model.Time, rule = Reserve_Capacity_Up_NA) 



"""
MATCHING DATA FROM CASE WITH MATHEMATICAL MODEL AND PRINTING DATA
"""
our_model = model.create_instance(data)   
our_model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT) #Import dual values into solver results
import pdb; pdb.set_trace()

"""
SOLVING PROBLEM
"""
opt = SolverFactory("gurobi", Verbose=True)
#opt.options['LogFile'] = 'gurobi_log.txt'

#start the timer
start_time = time.time()

results = opt.solve(our_model, tee=True)

#stop the timer
end_time = time.time()
running_time = end_time - start_time

"""
DISPLAY RESULTS??
"""

our_model.display('results.csv')
our_model.dual.display()
print("-" * 70)
print("Objective and running time:")
print(f"Objective value for this mongo model is: {round(pyo.value(our_model.Objective),2)}")
print(f"The instance was solved in {round(running_time, 4)} seconds🙂")
print("-" * 70)
print("Hardware details:")
print(f"Processor: {platform.processor()}")
print(f"Machine: {platform.machine()}")
print(f"System: {platform.system()} {platform.release()}")
#print(f"CPU Cores: {psutil.cpu_count(logical=True)} (Logical), {psutil.cpu_count(logical=False)} (Physical)")
#print(f"Total Memory: {psutil.virtual_memory().total / 1e9:.2f} GB")
print("-" * 70)
#import pdb; pdb.set_trace()



"""
EXTRACT VALUE OF VARIABLES AND WRITE THEM INTO EXCEL FILE
"""
"""
def save_results_to_excel(model_instance, filename="Variable_Results.xlsx"):
    
    # Saves Pyomo variable results into an Excel file with filtered output.
    # Only includes rows with non-zero or non-null values for variables.
    
    import pandas as pd
    from pyomo.environ import value

    # Create an Excel writer object
    with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
        # Loop over all active variables in the model
        for var in model_instance.component_objects(pyo.Var, active=True):
            var_name = var.name  # Get the variable name
            var_data = []
            
            # Collect variable data
            for index in var:
                try:
                    var_value = value(var[index])  # Safely get the variable value
                except ValueError:
                    var_value = 0  # If uninitialized, set to None
                if var_value:  # Include only non-zero and non-null values
                    var_data.append((index, var_value))
            
            # Transform data into a DataFrame
            if var_data:  # Only proceed if there is data
                df = pd.DataFrame(var_data, columns=["Index", var_name])
                
                # Dynamically unpack the indices into separate columns
                max_index_length = max(len(idx) if isinstance(idx, tuple) else 1 for idx, _ in var_data)
                unpacked_indices = pd.DataFrame(
                    [list(index) + [None] * (max_index_length - len(index)) if isinstance(index, tuple) else [index] for index, _ in var_data]
                )
                
                # Add unpacked indices to the DataFrame
                unpacked_indices.columns = [f"Index_{i+1}" for i in range(max_index_length)]
                df = pd.concat([unpacked_indices, df[var_name]], axis=1)
                
                # Write the filtered DataFrame to an Excel sheet
                df.to_excel(writer, sheet_name=var_name[:31], index=False)
    
    print(f"Variable results saved to {filename}")

# Usage after solving the model
save_results_to_excel(our_model, filename="Variable_Results.xlsx")
"""

"""
PLOT RESULTS
"""
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.cm import get_cmap
import numpy as np


def generate_unique_colors(num_colors, colormap='tab20'): #Generate a list of unique colors.
    cmap = get_cmap(colormap)
    return [cmap(i / num_colors) for i in range(num_colors)]


def plot_results_from_excel(input_file, output_folder):
    os.makedirs(output_folder, exist_ok=True)  # Create folder if it doesn't exist

    # Define mapping for Index_1 to Nodes names
    Nodes_mapping = {1: "Nodes 1", 2: "Nodes 2", 3: "Nodes 3"}

    # Read the Excel file
    excel_file = pd.ExcelFile(input_file)

    for sheet_name in excel_file.sheet_names:
        # Read the sheet
        df = pd.read_excel(excel_file, sheet_name=sheet_name)

        if sheet_name in ["x_aFRR_DWN", "x_aFRR_UP"]:
            # For x_aFRR_DWN and x_aFRR_UP, plot Index_1 vs. second column
            x_axis = df["Index_1"]
            y_axis = df.iloc[:, 1]  # Second column

            plt.figure(figsize=(12, 8))
            plt.plot(x_axis, y_axis, label=sheet_name, marker='o', color='blue')

            plt.title(f"{sheet_name}")
            plt.xlabel("Hours")
            plt.ylabel("Values")
            plt.legend(loc='best')
            plt.grid(True)

            # Save the plot
            plot_filename = f"{sheet_name}.png"
            plt.tight_layout()
            plt.savefig(os.path.join(output_folder, plot_filename))
            plt.close()

        elif sheet_name in ["x_aFRR_DWN_ind", "x_aFRR_UP_ind"]:
            if "Index_1" in df.columns and "Index_2" in df.columns:
                plt.figure(figsize=(12, 8))

                x_axis = df["Index_1"]
                value_column = df.columns[-1]  # Last column contains the values
                unique_variables = df["Index_2"].unique()
                colors = generate_unique_colors(len(unique_variables))

                for variable, color in zip(unique_variables, colors):
                    variable_data = df[df["Index_2"] == variable]
                    plt.plot(
                        variable_data["Index_1"], variable_data[value_column],
                        label=variable, marker='o', color=color
                    )

                plt.title(f"{sheet_name}")
                plt.xlabel("Hours")
                plt.ylabel("Values")
                plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3, title="Variables", borderaxespad=0.)
                plt.grid(True)

                # Save the plot
                plot_filename = f"{sheet_name}.png"
                plt.tight_layout()
                plt.savefig(os.path.join(output_folder, plot_filename))
                plt.close()

        else:
            if "Index_1" in df.columns and "Index_2" in df.columns:
                unique_index_1 = df["Index_1"].unique()

                for index_1_value in unique_index_1:
                    filtered_df = df[df["Index_1"] == index_1_value]
                    x_axis = filtered_df["Index_2"]

                    plt.figure(figsize=(12, 8))

                    if "Index_3" in filtered_df.columns:
                        variable_column = "Index_3"
                        value_column = df.columns[-1]
                        unique_variables = filtered_df[variable_column].unique()
                        colors = generate_unique_colors(len(unique_variables))

                        for variable, color in zip(unique_variables, colors):
                            variable_data = filtered_df[filtered_df[variable_column] == variable]
                            plt.plot(
                                variable_data["Index_2"], variable_data[value_column],
                                label=variable, marker='o', color=color
                            )

                        plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3, title="Variables", borderaxespad=0.)
                    else:
                        value_column = df.columns[-1]
                        plt.plot(filtered_df["Index_2"], filtered_df[value_column], label=value_column, marker='o', color='blue')

                    # Use Nodes mapping for title
                    Nodes_name = Nodes_mapping.get(index_1_value, f"Index_1 = {index_1_value}")
                    plt.title(f"{sheet_name} ({Nodes_name})")
                    plt.xlabel("Hours")
                    plt.ylabel("Values")
                    plt.grid(True)

                    plot_filename = f"{sheet_name}_{Nodes_name.replace(' ', '_')}.png"
                    plt.tight_layout()
                    plt.savefig(os.path.join(output_folder, plot_filename))
                    plt.close()
                    


# Usage
if __name__ == "__main__":
    input_excel_file = "Variable_Results.xlsx"  # Path to the Excel file
    output_plots_folder = "plots"  # Folder to save the plots

    # Generate plots
    #plot_results_from_excel(input_excel_file, output_plots_folder)


def extract_demand_and_flex_demand(model):
    demand_data = []
    flex_demand_data = []

    for s in model.Nodes:
        for t in model.Time:
            for e in model.EnergyCarrier:
                if e == "Electricity":  # Restrict to Electricity for this use case
                    # Retrieve the values safely
                    demand_value = pyo.value(model.Demand[s, t, e])
                    flex_demand_value = (
                        demand_value
                        + sum(pyo.value(model.q_charge[s, t, b]) for b in model.FlexibleLoad if (b, e) in model.ShiftableLoadForEnergyCarrier)
                        - sum(pyo.value(model.q_discharge[s, t, b]) for b in model.FlexibleLoad if (b, e) in model.ShiftableLoadForEnergyCarrier)
                    )

                    # Append to lists
                    demand_data.append({'Nodes': s, 'Time': t, 'EnergyCarrier': e, 'Demand': demand_value})
                    flex_demand_data.append({'Nodes': s, 'Time': t, 'EnergyCarrier': e, 'flex_demand': flex_demand_value})

    # Convert to DataFrame
    demand_df = pd.DataFrame(demand_data)
    flex_demand_df = pd.DataFrame(flex_demand_data)

    return demand_df, flex_demand_df
 # Get the data
demand_df, flex_demand_df = extract_demand_and_flex_demand(our_model)

# Merge the DataFrames for unified plotting
merged_df = pd.merge(demand_df, flex_demand_df, on=['Nodes', 'Time', 'EnergyCarrier'])

# Plotting
plt.figure(figsize=(12, 6))
for Nodes in merged_df['Nodes'].unique():
    Nodes_data = merged_df[merged_df['Nodes'] == Nodes]
    plt.step(Nodes_data['Time'], Nodes_data['Demand'],label=f'Demand - Nodes {Nodes}')
    plt.step(Nodes_data['Time'], Nodes_data['flex_demand'], "--", label=f'Flex Demand - Nodes {Nodes}')

plt.xlabel('Time')
plt.ylabel('Demand (MW)')
plt.title('Demand and Flexible Demand Over Time')
plt.legend()
plt.grid(True)
plt.show()
"""