*** Settings ***
Documentation     A resource file with common reusable keywords and variables.

Library           Selenium2Library
Library           OperatingSystem
Library           Collections
Library           Utils


*** Variables ***
${SERVER}                   192.168.33.114
${BROWSER}                  Chrome
${ADMIN PASSWORD}           admin
${TIMEOUT}                  8 s
${MAIN URL}                 https://${SERVER}/

*** Keywords ***
Open Browser To Kuberdock Page
    Prepare And Open Browser    ${BROWSER}    ${MAIN URL}
    Login Page Should Be Open

Login Page Should Be Open
    Wait Until Page Contains Element    jquery=button:contains(Log in)


Input Username "${username}"
    Input Text    css=#login-form-username-field    ${username}

Input Password "${password}"
    Input Text    css=#login-form-password-field    ${password}

Submit Credentials
    Click Button    css=button.login

Login into the Kuberdock as "${username}" with password "${password}"
    Input Username "${username}"
    Input Password "${password}"
    Submit Credentials

Login into the Kuberdock
    Login into the Kuberdock as "admin" with password "${ADMIN PASSWORD}"
    Nodes View Should Be Open

Exit Login As Mode
    Click Element    jquery=.login-view-mode-wrapper span:contains(Exit Mode)
    Breadcrumb Should Contain "Users"

Logout
    Click Element    jquery=.profile-menu a
    Wait Until Element Is Visible And Click    jquery=.navbar span:contains(Logout)
    Login Page Should Be Open


Breadcrumb Should Contain "${text}"
    Wait Until Page Contains Element    jquery=ul.breadcrumb:contains("${text}")

Pods View Should Be Open
    Breadcrumb Should Contain "Pods"

Nodes View Should Be Open
    Breadcrumb Should Contain "Nodes"

Users View Should Be Open
    Breadcrumb Should Contain "Users"



Page Should Not Contain Error Messages
    Page Should Not Contain Element    jquery=.notify-msg

Page Should Contain Error Message "${text}"
    Wait Until Page Contains Element    jquery=.notify-msg:contains("${text}")

Page Should Contain Only Error Message "${text}"
    Page Should Contain Error Message "${text}"
    ${elements}=    Get Webelements    jquery=.notify-msg
    Length Should Be    ${elements}    1    There is more than one error message.
    Page Should Not Contain Element    jquery=.notify-multi    There is more than one error message.

Close Error Message "${text}"
    Click Element    jquery=.notify-msg:contains("${text}") ~ .notify-close
    Wait Until Page Does Not Contain Element    jquery=.notify-msg:contains("${text}")

Wait Until Element Is Visible And Click
    [Arguments]    ${locator}
    Wait Until Element Is Visible    ${locator}
    Click Element    ${locator}

Click "${button}" In Modal Dialog
    Wait Until Element Is Visible And Click    jquery=.modal.in button:contains("${button}")

Go to the Users page
    Wait Until Keyword Succeeds    ${TIMEOUT}    0.1s
    ...    Click Element    jquery=.navbar a:contains(Administration)
    Wait Until Element Is Visible And Click    jquery=.navbar a:contains(Users)
    Users View Should Be Open

Login as "${username}"
    Click Element    jquery=#userslist-table a:contains("${username}")
    Breadcrumb Should Contain "${username}"
    Click Element    jquery=button:contains(Login as this user)
    Click "Ok" In Modal Dialog

All pods should be "${status}"
    Wait Until Page Does Not Contain Element
    ...    jquery=#podlist-table tr td:nth-of-type(3):not(:contains(${status}))
