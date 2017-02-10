*** Settings ***
Documentation     A resource file for billing tests steps on WHMCS admin side

Resource          global_resources.robot
Resource          ./whmcs_user_resource.robot
Resource          ./kd_admin_resource.robot
Resource          ./kd_user_resource.robot

Library           Selenium2Library
Library           Utils
Library           SSHLibrary



*** Keywords ***
Open WHMCS Admin's Browser
    Open Browser  ${WHMCS ADMIN URL}  ${BROWSER}    alias=WHMCSadmin
    Wait Until Page Contains Element    jquery=h2:contains(Login)  15 sec


Login WHMCS admin
    Input Text  xpath=//input[@name='username']   ${WHMCS LOGIN}
    Input Text  xpath=//input[@name='password']    ${WHMCS PASSWORD}
    Click  xpath=//input[@name='rememberme']
    Click  xpath=//input[@value='Login']
#    Wait Until Page Contains  Admin Summary
    Wait Until Element Is Visible  css=a[href="supporttickets.php"]
    # Close Popup
    ${present}=  Run Keyword And Return Status    Element Should Be Visible   css=#dl1
    Run Keyword If    ${present}    Close Popup


Configire WHMCS Package
    [Arguments]  ${package type}  ${billing type}  ${ip_price}  ${ps_price}  ${action}
    ...  ${tiny}  ${standard}  ${high_memory}
    Go to WHMCS product page  ${package type}

    Run Keyword If  '${package type}'=='Trial'
    ...  Select Trial Packege Checkbox

    Run Keyword If  '${package type}'=='Standard package'
    ...  Set Price for IP  ${ip_price}  ${package type}
    Run Keyword If  '${package type}'=='Standard package'
    ...  Set Price for Persistent Storage  ${ps_price}  ${package type}

    Run Keyword If  '${package type}'=='Standard package'
    ...  Set WHMCS billing type   ${billing type}
    Set WHMCS "Automatically Setup The Product" Type  ${action}

    Save WHMCS Product Settings

    Run Keyword If  '${package type}'=='Standard package'
    ...  Set Kubes Prices for Standard Package  ${tiny}  ${standard}  ${high_memory}
    Run Keyword If  '${package type}'=='Trial'
    ...  Set Kubes Prices for Trial Package  ${tiny}  ${standard}  ${high_memory}


${Action} Trial Packege Checkbox
    ${condition}=  Set Variable If  '${Action}'=='Select'  Should Not
    ...                             '${Action}'=='Unselect'  Should
    ${present}=  Run Keyword And Return Status    Checkbox ${condition} Be Selected
    ...  css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}
    ...  Click  name=packageconfigoption[1]


Go to WHMCS product page
    [Arguments]  ${package type}
    ${path}=  Set Variable If
    ...  '${package type}'=='Standard package'  2
    ...  '${package type}'=='Trial'  3
    Scroll Page To Location    0    -2000
    Go to WHMCS Products List Page
    Click  xpath=(//img[@alt='Edit'])[${path}]
    Wait Until Page Contains Element  css=input[value="${package type}"]  15 s
    Unselect "Hiden" check-box if it's selected
    # Select by default 'Logs on "Module Log" ' check-box if not selected
    Scroll Page To Location    0    -2000
    Click  id=tabLink3
    Select "Module Log" Checkbox  ${package type}


Unselect "Hiden" check-box if it's selected
    Scroll Page To Location    0    2000
    ${present}=  Run Keyword And Return Status    Element Should Be Visible
    ...          css=.fieldarea input[checked=""]
    Run Keyword If    ${present}    Click  css=.fieldarea input[checked=""]


Select "Module Log" Checkbox
    [Arguments]  ${package type}
    ${present}=  Run Keyword And Return Status    Checkbox Should Be Selected
    ...  css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}  Unselect Trial Packege Checkbox

    ${present}=  Run Keyword And Return Status    Checkbox Should Not Be Selected
    ...          css=input[name="packageconfigoption[4]"]
    Run Keyword If    ${present}    Click  css=input[name="packageconfigoption[4]"]


Go to WHMCS Products List Page
    Sleep  4
    Mouse Over  id=Menu-Setup
    Click  id=Menu-Setup-Products_Services
    Click  id=Menu-Setup-Products_Services-Products_Services
    Wait Until Page Contains Element  id=Create-Product-link  15 s


Set WHMCS billing type
    [Arguments]   ${billing type}
    # Go to "Module Settings" tab if its's not selected
    ${present}=  Run Keyword And Return Status    Element Should Not Be Visible
    ...          css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}    Click  id=tabLink3
    Click  css=input[value="${billing type}"]


Set Price for IP
    [Arguments]  ${ip_price}  ${package type}
    # Go to "Module Settings" tab if its's not selected
    ${present}=  Run Keyword And Return Status    Element Should Not Be Visible
    ...          css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}    Click  id=tabLink3
    Clear Element Text  name=packageconfigoption[5]
    Input Text  name=packageconfigoption[5]   ${ip_price}
    Run Keyword If  '${package type}'=='Standard package'
    ...  Set Test Variable    ${IP PRICE}    ${ip_price}


Set Price for Persistent Storage
    [Arguments]    ${ps_price}  ${package type}
    # Go to "Module Settings" tab if its's not selected
    ${present}=  Run Keyword And Return Status    Element Should Not Be Visible
    ...          css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}    Click  id=tabLink3
    Clear Element Text  name=packageconfigoption[6]
    Input Text  name=packageconfigoption[6]   ${ps_price}
    Run Keyword If  '${package type}'=='Standard package'
    ...  Set Test Variable    ${PS PRICE}    ${ps_price}


Set WHMCS "Automatically Setup The Product" Type
    [Arguments]  ${action}
    # Go to "Module Settings" tab if its's not selected
    ${present}=  Run Keyword And Return Status    Element Should Not Be Visible
    ...          css=input[name="packageconfigoption[1]"]
    Run Keyword If    ${present}    Click  id=tabLink3
    Click  jquery=label:contains('${action}')


Save WHMCS Product Settings
    Scroll Page To Location    0    2000
    Click  css=input[value="Save Changes"]


Set Kubes Prices for Standard Package
    [Arguments]  ${tiny}  ${standard}  ${high_memory}
    Go to Addons Page
    # Set price for tiny kube
    Set Price of One Kube Type for Package  Standard  1  0  ${tiny}
    Set Test Variable    ${TINY KUBE PRICE FOR STANDARD PACK}    ${tiny}
    # Set price for standard kube
    Set Price of One Kube Type for Package  Standard  3  1  ${standard}
    Set Test Variable    ${STANDARD KUBE PRICE FOR STANDARD PACK}    ${standard}
    # Set price for high memmory kube
    Set Price of One Kube Type for Package  Standard  5  2  ${high_memory}
    Set Test Variable    ${HIGH MEMMORY KUBE PRICE FOR STANDARD PACK}    ${high_memory}


Set Kubes Prices for Trial Package
    [Arguments]  ${tiny}  ${standard}  ${high_memory}
    Go to Addons Page
    # Set price for tiny kube
    Set Price of One Kube Type for Package  Trial  1  0  ${tiny}
    Set Test Variable    ${TINY KUBE PRICE FOR TRIAL PACK}    ${tiny}
    # Set price for standard kube
    Set Price of One Kube Type for Package  Trial  3  1  ${standard}
    Set Test Variable    ${STANDARD KUBE PRICE FOR TRIAL PACK}    ${standard}
    # Set price for high memmory kube
    Set Price of One Kube Type for Package  Trial  5  2  ${high_memory}
    Set Test Variable    ${HIGH MEMMORY KUBE PRICE FOR TRIAL PACK}    ${high_memory}


Go to Addons Page
    Mouse Over  id=Menu-Addons
    Click  jquery=a:contains('KuberDock addon')
    Page Should Contain Element  jquery=h1:contains('KuberDock addon')


Set Price of One Kube Type for Package
    [Arguments]  ${package type}  ${path 1}  ${path 3}  ${kube type}
    # Check whitch typy of WHMCS Package
    ${path 2}=  Set Variable If
    ...         '${package type}'=='Standard'  0
    ...         '${package type}'=='Trial'     1

    # Click "Pricing settings" button
    Click  xpath=.//*[@id='kubes_table']/tbody/tr[${path 1}]/td[1]/span

    # Select "Active" checkbox if it is not select
    ${present}=  Run Keyword And Return Status    Element Should Not Be Visible
    ...          css=input#active_kube_checkbox_${path 2}_${path 3}[checked="checked"]
    Run Keyword If    ${present}    Click  css=input#active_kube_checkbox_${path 2}_${path 3}

    # Input text
    Clear Element Text  id=price_input_${path 2}_${path 3}
    Sleep  1 sec
    Input Text  id=price_input_${path 2}_${path 3}   ${kube type}
    Click  xpath=//tr[@id='package_${path 3}']//input[@id='price_input_${path 2}_${path 3}']/following-sibling::span//button[.='Save']
    Scroll Page To Location    0    2000



Delete WHMCS User
    Go to WHMCS ${user first name} Profile Page
    Scroll Page To Location    0    2000
    Click  css=a[onclick="deleteClient();return false"]
    Sleep  1
    Confirm Action
    Capture Page Screenshot
    Page Should Not Contain  ${user first name}


Go to WHMCS ${user first name} Profile Page
    Click  id=Menu-Clients
    Wait Until Page Contains Element  jquery=h1:contains(View/Search Clients)  15 sec
    Capture Page Screenshot
    Click  jquery=a:contains(${user first name})
    Wait Until Page Contains Element  jquery=h1:contains(Client Profile)  15 sec
    ${whmcs user id}=  Get Text  id=userId
    Set Test Variable  ${whmcs user id}


Close Popup
    Click    css=.donotshow>label
    Click    css=.close


Add Money To WHMCS User Account For Buy Pod
    Go to WHMCS ${user first name} Profile Page
    Open Browser
    ...  http://whmcs.some.com/admin/clientscredits.php?userid=${whmcs user id}
    ...  ${BROWSER}    alias=CreditManagement
    Input Text  xpath=//input[@name='username']   ${WHMCS LOGIN}
    Input Text  xpath=//input[@name='password']    ${WHMCS PASSWORD}
    Click  xpath=//input[@name='rememberme']
    Click  xpath=//input[@value='Login']
    Wait Until Page Contains Element    jquery=h2:contains(Credit Management)  10 s
    Click  css=input[value="Add Credit"]
    Clear Element Text  css=input[value="0.00"]
    ${money amount}=  Convert To Integer  ${test expected price}
    Input Text  css=input[value="0.00"]  ${money amount}
    Click  css=input[value="Save Changes"]
    Capture Page Screenshot
    Close Browser


Synchronize Server Time On KD and WHMCS
    Login KD Server Via SSH
    Run Synchronize Time Commands
    Login WHMCS Server Via SSH
    Run Synchronize Time Commands


Run Synchronize Time Commands
    ${stop ntpd}=   Execute Command    systemctl stop ntpd
    Should Not Contain  ${stop ntpd}  Failed

    ${ntpd}=        Execute Command    ntpd -gq
    Should Contain  ${ntpd}  ntpd: time

    ${start ntpd}=  Execute Command    systemctl start ntpd
    Should Not Contain  ${start ntpd}  Failed


Login WHMCS Server Via SSH
    [Arguments]  ${whmcs server hostname}=${WHMCS SERVER HOSTNAME}  ${whmcs ssh login}=${WHMCS SSH LOGIN}
    ...          ${whmcs ssh password}=${WHMCS SSH PASSWORD}
    Open Connection  ${whmcs server hostname}  alias=WHMCS_Server  timeout=60 sec
    Login  ${whmcs ssh login}  ${whmcs ssh password}


Change WHMCS Server Time to ${number 1} Month and ${number 2} Days Forward and Run Cron Script
    Switch Connection  WHMCS_Server
    ${date 1}=   Execute Command  date --set '+${number 1} months'
    Run Cron Script
    ${date 2}=   Execute Command  date --set '+${number 2} days'
    Run Cron Script


Run Cron Script
    ${cron}=   Execute Command  php -q ${WHMCS PATH}/crons/cron.php
    Log  ${cron}
    Should Contain  ${cron}  Goodbye

Go To Invoices Tab
    Scroll Page To Location    0    -2000
    ${present}=  Run Keyword And Return Status
    ...  Element Should Be Visible   css=.nav.nav-tabs.client-tabs .dropdown-toggle
    Run Keyword If  ${present}  Click  css=.nav.nav-tabs.client-tabs .dropdown-toggle
    Click  id=clientTab-7


Check New Invoice
    [Arguments]  ${expected status}
    Go To Invoices Tab
    Scroll Page To Location    0    2000
    ${actual status}  Get Text  xpath=.//*[@id='sortabletbl1']/tbody/tr[2]/td[8]/span
    ${is status ok}=  Evaluate  '${expected status}' == '${actual status}'
    Log  ${is status ok}
    Run Keyword If  ${is status ok} == False  Fail
    ...   QA: Incorrect invoice status!!!
    ${invoice actual price}  Get Text  xpath=.//*[@id='sortabletbl1']/tbody/tr[2]/td[6]/a
    Set Actual Price by Convert Screen Price Text to Integer  ${invoice actual price}
    Comparison of Actual Prices to the Expected


Mark Invoice As Paid
    Select Checkbox  xpath=.//*[@id='sortabletbl1']/tbody/tr[2]/td[1]/input
    Click  css=input[value="Mark Paid"]
    Sleep  1
    Confirm Action
    Wait Until Element Is Visible  css=.successbox  20 s
