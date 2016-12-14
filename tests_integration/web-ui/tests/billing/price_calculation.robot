*** Settings ***
Documentation     A resource file with price calcilation for different APPs.

Resource          whmcs_admin_resource.robot


*** Variables ***


*** Keywords ***
Get "${app name}" Prices
    # Change the the amount of resources here
    Set Variable According to the Formula by ${app name} YAML Values

    # APPLICATION "S" AP_PACKAGE PRICE
    ${application s ap_package price}=  Evaluate
    ...  ${IP PRICE} + (${PS COUNT "S"} * ${PS PRICE}) + (${KUBES COUNT "S"} * ${TINY KUBE PRICE FOR STANDARD PACK})
    Set Test Variable  ${APPLICATION S AP_PACKAGE PRICE}  ${application s ap_package price}

    # APPLICATION "M" AP_PACKAGE PRICE
    ${application m ap_package price}=  Evaluate
    ...  ${IP PRICE} + (${PS COUNT "M"} * ${PS PRICE}) + (${KUBES COUNT "M"} * ${STANDARD KUBE PRICE FOR STANDARD PACK})
    Set Test Variable  ${APPLICATION M AP_PACKAGE PRICE}  ${application m ap_package price}

    # APPLICATION "L" AP_PACKAGE PRICE
    ${application l ap_package price}=  Evaluate
    ...  ${IP PRICE} + (${PS COUNT "L"} * ${PS PRICE}) + (${KUBES COUNT "L"} * ${HIGH MEMMORY KUBE PRICE FOR STANDARD PACK})
    Set Test Variable  ${APPLICATION L AP_PACKAGE PRICE}  ${application l ap_package price}

    # Log for check
    Log  ${APPLICATION S AP_PACKAGE PRICE}
    Log  ${APPLICATION M AP_PACKAGE PRICE}
    Log  ${APPLICATION L AP_PACKAGE PRICE}

Set Variable According to the Formula by ${app name} YAML Values
    Run Keyword If  '${app name}'=='Dokuwiki'
    ...  Set Coefficient Variables  5  2  5  2  6  2
#    ...  ELSE IF    '${app name}'==''  Set Coefficient Variables

Set Coefficient Variables
    [Arguments]  ${ps count "s"}  ${kubes count "s"}
    ...  ${ps count "m"}  ${kubes count "m"}  ${ps count "l"}  ${kubes count "l"}
    Set Test Variable  ${PS COUNT "S"}       ${ps count "s"}
    Set Test Variable  ${KUBES COUNT "S"}    ${kubes count "s"}
    Set Test Variable  ${PS COUNT "M"}       ${ps count "m"}
    Set Test Variable  ${KUBES COUNT "M"}    ${kubes count "m"}
    Set Test Variable  ${PS COUNT "L"}       ${ps count "l"}
    Set Test Variable  ${KUBES COUNT "L"}    ${kubes count "l"}

