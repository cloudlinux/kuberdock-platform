*** Settings ***
Documentation     A resource file for billing tests steps on WHMCS user side

Resource          global_resources.robot
Resource          ./whmcs_admin_resource.robot
Resource          ./kd_admin_resource.robot
Resource          ./kd_user_resource.robot

Library           Selenium2Library
Library           Utils
Library           String



*** Keywords ***
Make Check in WHMCS
    [Arguments]  ${user type}  ${expected invoice status}  ${app name}=${APP NAME}
    ...   ${billing type}=${BILLING TYPE}
    Make Check in Cart  ${user type}  ${app name}  ${billing type}
    Invoice Should Have "${expected invoice status}" Status
    Ckeck Price in WHMCS Invoice


Make Check in Cart
    [Arguments]  ${user type}  ${app name}=${APP NAME}  ${billing type}=${BILLING TYPE}
    Check "${app name}" price in WHMCS cart
    Ckeck Item Price in WHMCS Cart
    Check '${billing type}' Order Summary
    Confirm Order on WHMCS  ${user type}



Check "${app name}" price in WHMCS cart
    Wait Until Page Contains Element    id=orderSummary  30 s
    Wait Until Page Contains Element  jquery=span:contains(${app name})  15 s


Ckeck Item Price in WHMCS Cart
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=
    ...  Get Text  xpath=.//*[@id='order-standard_cart']/div/div[3]/div[2]/div[1]/form/div[2]/div/div/div[2]/span[1]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Expected price is set on PA order page №2
    Comparison of Actual Prices to the Expected


Check '${billing type}' Order Summary
    Run Keyword If  '${billing type}'=='Fixed Price'  Fixed Price Order Summary
    ...   ELSE IF   '${billing type}'=='PAYG'  PAYG Order Summary


Fixed Price Order Summary
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=
    ...  Get Text  xpath=.//*[@id='orderSummary']/div/div[2]/span[1]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Expected price is set on PA order page №2
    Comparison of Actual Prices to the Expected


PAYG Order Summary
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=
    ...  Get Text  xpath=.//*[@id='orderSummary']/div/div[2]/span[1]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Expected price is set on PA order page №2
    ${payg expected price}=  Set variable  0
    ${is price ok}=  Evaluate  ${test actual price} == ${payg expected price}
    Log  ${is price ok}
    Run Keyword If  ${is price ok} == False  Fail
    ...   Comparison of actual prices to the expected is FAIL

Confirm Order on WHMCS
    [arguments]  ${user type}
    Scroll Page To Location    0    2000
    Click  id=checkout
    Wait Until Page Contains  Please enter your personal details and billing information to checkout.  15 s
    Run Keyword If  '${user type}'=='New User'  Fill WHMCS User Register Form And Complete Order
    ...  ELSE IF  '${user type}'=='Registered User'  Click  id=btnCompleteOrder
    Wait Until Page Contains Element  css=.invoice-status  15 s


Fill WHMCS User Register Form And Complete Order
    # "First Name" Field
    ${user first name}=  Generate Random String  8  [LETTERS]
    Input Text  id=inputFirstName  ${user first name}
    Set Test Variable  ${user first name}
    # "Last Name" Field
    ${last name}=  Generate Random String  8  [LETTERS]
    Input Text  id=inputLastName  ${last name}
    # "Email Address" Field
    ${random_email}=  Generate Random String  8
    ${user email address}=  Set Variable  ${random_email}@test.com
    Input Text  id=inputEmail  ${user email address}
    Set Test Variable  ${user email address}
    # "Phone Number" Field
    ${phone number}=  Generate Random String  8  [NUMBERS]
    Input Text  id=inputPhone  ${phone number}
    # "Street Address" Field
    ${street address}=  Generate Random String  8  [LETTERS]
    Input Text  id=inputAddress1  ${street address}
    # "City" Field
    ${city}=  Generate Random String  8  [LETTERS]
    Input Text  id=inputCity  ${city}
    # "State" Field
    Click  id=stateselect
    Click  jquery=option:contains(California)
    # "Postcode" Field
    ${Postcode}=  Generate Random String  8
    Input Text  id=inputPostcode  ${Postcode}
    # "Password" Field
    ${password}=  Generate Random String  25
    Input Text  id=inputNewPassword1  ${password}
    # "Confirm Password" Field
    Input Text  id=inputNewPassword2  ${password}
    # Confirm Order
    Click  id=btnCompleteOrder


Ckeck Price in WHMCS Invoice
    Scroll Page To Location    0    2000
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=
    ...  Get Text  xpath=html/body/div[1]/div[5]/div/table/tbody/tr[2]/td[2]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Expected price is set on PA order page №2
    Comparison of Actual Prices to the Expected


Get Invoice Status
    Capture Page Screenshot
    # Get actual price from screen
    ${actual invoice status}=
    ...  Get Text  xpath=html/body/div[1]/div[1]/div[2]/div[1]/span
    Set Test Variable  ${actual invoice status}


Invoice Should Have "${expected invoice status}" Status
    Get Invoice Status
    Run Keyword If  '${actual invoice status}' != '${expected invoice status}'
    ...  Fail  Invoice has incorrect status


Pay For Invoice
    Reload Page
    Capture Page Screenshot
    Click  css=input[value="Apply Credit"]  0.2 s  10 s