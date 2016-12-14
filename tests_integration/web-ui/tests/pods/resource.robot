*** Settings ***
Documentation     A resource file for pods tests

Resource          global_resources.robot
Resource          ../users/resource.robot
Resource          ../billing/whmcs_admin_resource.robot

Library           String

*** Keywords ***
Delete New Pod
    Click    jquery=span.terminate-btn
    Click "Delete" In Modal Dialog
    Wait Until Page Contains Element    jquery=td.text-center:contains(You don't have any pods)

Create Pod From Docker Hub Using Container Image
    [Arguments]     ${image}    ${open ports}=Don't Open Ports    ${start}=Don't Start It
    Begin Pod Creation
    Add ${image} Container From Docker Hub
    Run Keyword If    "${open ports}"=="Open Ports"    Open All Ports
    Save Pod
    Wait Until Pod Is Saved
    Run Keyword If    "${start}"=="Start It"      Start New Pod

Start New Pod
    Click    jquery=span.start-btn
    Wait Until Page Contains Element    jquery=span:contains(pending)    timeout=20
    Wait Until Page Contains Element    jquery=span:contains(running)    timeout=600

Go To New Pod's Page
    Click   jquery=a:contains(New Pod)

Begin Pod Creation
    Click    jquery=a:contains(Add new container)
    Breadcrumb Should Contain "New Pod"

Add ${image} Container From Docker Hub
    Click    xpath=//button[@data-toggle='dropdown']
    Click    jquery=a:contains(Docker Hub)
    Input text    jquery=input#search-image-field    ${image}
    Click    jquery=button.search-image
    Click    jquery=button:contains(Select)

Save Pod
    Click    jquery=button:contains(Next)
    Click    jquery=button:contains(Next)
    Click    jquery=button:contains(Save)

Wait Until Pod Is Saved
    Breadcrumb Should Contain "Pods"
    Wait Until Page Contains Element    jquery=a:contains(New Pod)    timeout=20
    Wait Until Page Contains Element    jquery=span:contains(stopped)    timeout=20
    Wait Until Page Contains Element    jquery=td:contains(Standard)    timeout=20

Go Back To KuberDock Tab
    Select Window  title=KuberDock

Go To User's Pods Page
    Click   jquery=li.bpoint-pods > a:contains(Pods)

Access New Pod's Public IP ${times} Times
    # Click                   jquery=div.col-md-6 > div:contains(Public IP):first-child > a
    Click                   jquery=a.pod-public-address
    Get Window Titles
    Select Window           title=Welcome to nginx!
    Page Should Contain     Thank you for using nginx.
    :FOR  ${val}  IN RANGE  0  ${times}
    \       Reload Page
    \       Page Should Contain     Thank you for using nginx.
    \       Sleep                   2

    Close Window
    Go Back To KuberDock Tab

Go To New Pod's ${container} Container Page And Wait For ${number} Access Logs To Appear
    Click   jquery=a:contains(${container})
    Wait Until Keyword Succeeds    2 m    20 s    Locator Should Match X Times    jquery=div.container-logs > p:contains(GET / HTTP/1.1)  ${number}

Open All Ports
    Wait Until Page Contains Element    jquery=thead:contains(Container port)
    @{check_boxes}  Get Webelements  css=td.public > label.custom > span
    :FOR  ${check_box}  IN  @{check_boxes}
    \    Click Element  ${check_box}

Delete Pod On Pod Info Page
    Click  jquery=span:contains(Manage pod)
    Click  jquery=span:contains(Delete)
    Click  jquery=button:contains(Delete)
    Sleep  1.5 s
    Wait Until Element Is Not Visible  css=.loader  15 s
    Sleep  0.5 s
    Breadcrumb Should Contain "Pods"
