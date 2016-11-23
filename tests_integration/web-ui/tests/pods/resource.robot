*** Settings ***
Documentation     A resource file for pods tests

Resource          global_resources.robot
Resource          ../users/resource.robot

Library           String

*** Keywords ***
Select billing status "${value}"
    Go to the Settings page
    Click    jquery=a:contains(Billing)
    Click    jquery=button[data-id="billing_type"]
    Click    jquery=a:contains("${value}")
    Click    jquery=button:contains(Save)

Delete New Pod
    Click    jquery=span.terminate-btn
    Click "Delete" In Modal Dialog
    Wait Until Page Contains Element    jquery=td.text-center:contains(You don't have any pods)

Create Pod With ${value} Container From Docker Hub And Start It
    Click    jquery=a:contains(Add new container)
    Breadcrumb Should Contain "New Pod"
    Click    xpath=//button[@data-toggle='dropdown']
    Click    jquery=a:contains(Docker Hub)
    Input text    jquery=input#search-image-field    ${value}
    Click    jquery=button.search-image
    Click    jquery=button:contains(Select)
    Click    jquery=button:contains(Next)
    Click    jquery=button:contains(Next)
    Click    jquery=button:contains(Save)
    Breadcrumb Should Contain "Pods"
    Wait Until Page Contains Element    jquery=a:contains(New Pod)    timeout=10
    Wait Until Page Contains Element    jquery=span:contains(stopped)    timeout=10
    Wait Until Page Contains Element    jquery=td:contains(Standard)    timeout=10
    Click    jquery=span.start-btn
    Wait Until Page Contains Element    jquery=span:contains(pending)    timeout=10
    Wait Until Page Contains Element    jquery=span:contains(running)    timeout=600
