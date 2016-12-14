*** Settings ***
Documentation     A resource file for billing tests steps on KuberDock admin side

Resource          global_resources.robot
Resource          ./whmcs_admin_resource.robot
Resource          ./whmcs_user_resource.robot
Resource          ./kd_user_resource.robot

Library           Selenium2Library
Library           Utils


*** Keywords ***
Open KuberDock Admin's Browser
    Open Browser  ${MAIN URL}  ${BROWSER}  alias=KuberDockAdmin
    Login Page Should Be Open


Select KD settings to use WHMCS billing
    [Arguments]  ${WHMCS URL}  ${WHMCS LOGIN}  ${WHMCS PASSWORD}
    Select billing type "WHMCS"
    Fill And Save WHMCS Data For Authorization  ${WHMCS URL}  ${WHMCS LOGIN}
    ...  ${WHMCS PASSWORD}


Select billing type "${value}"
    Go to the Settings page
    Click    jquery=a:contains(Billing)
    Click    jquery=button[data-id="billing_type"]
    Click    jquery=a:contains("${value}")
    Run Keyword If    $value == "No billing"    Click    jquery=button:contains(Save)


Fill And Save WHMCS Data For Authorization
    [Arguments]  ${WHMCS URL}  ${WHMCS LOGIN}  ${WHMCS PASSWORD}
    Input "${WHMCS URL}" in "Link to billing" field
    Input "${WHMCS LOGIN}" in "Billing admin username" field
    Input "${WHMCS PASSWORD}" in "Billing admin password" field
    Click  jquery=button:contains(Save)
     ${present}=  Run Keyword And Return Status    Element Should Be Visible
    ...          id=message-header-text
    Run Keyword If    ${present}    Click  css=#message-header .toggler
    Click  jquery=a:contains(General)
    Input "${SECRET KEY}" in "Secret key for Single sign-on" field
    Click  jquery=button:contains(Save)


Generate PA Order Page Link
    [Arguments]  ${app name}=${APP NAME}
    Go to the Predefined Apps page
    # Search PA YAML on no-first page
    Click  id=nav-search
    Wait Until Element Is Visible  id=nav-search-input
    Input Text  id=nav-search-input  ${app name}
    Wait Until Element Is Visible
    ...  xpath=//span[@data-original-title='Copy ${app name} link app']
    Click  xpath=//span[@data-original-title='Copy ${app name} link app']
    Page Should Contain  Link copied to buffer
    ${link}=    PA Order Page Link
    Set Test Variable    ${PA LINK}    ${link}


Delete Test's IP Pool
    Switch Browser  KuberDockAdmin
    Delete IP Pool

Login KD Server Via SSH
    [Arguments]  ${kd server hostname}=${SERVER}  ${kd ssh login}=${KD SSH LOGIN}
    ...          ${kd ssh password}=${KD SSH PASSWORD}
    Open Connection  ${kd server hostname}  alias=KD_Server  timeout=60 sec
    Login  ${kd ssh login}  ${kd ssh password}

