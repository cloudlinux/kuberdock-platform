*** Settings ***
Documentation     A resource file for billing tests steps on KuberDock user side

Resource          global_resources.robot
Resource          ./whmcs_admin_resource.robot
Resource          ./whmcs_user_resource.robot
Resource          ./kd_admin_resource.robot

Library           Selenium2Library
Library           Utils


*** Keywords ***
Try To Buy PA Package and Check Prices
    [Arguments]  ${letter}  ${s ap_package price for app}
    ...  ${m ap_package price for app}  ${l ap_package price for app}
    Open KuberDock User's Browser
    ...  ${s ap_package price for app}   ${l ap_package price for app}
    ...  ${m ap_package price for app}
    Select AppPackage
    ...    ${letter}  ${s ap_package price for app}
    ...    ${l ap_package price for app}  ${m ap_package price for app}




Open KuberDock User's Browser
    [Arguments]
    ...  ${s ap_package price for app}  ${m ap_package price for app}
    ...  ${l ap_package price for app}
    Open Browser  ${PA LINK}  ${BROWSER}  alias=KuberDockUser
    Page Should Contain  You are installing the application
    # Check price of S appPackage
    Check AppPackage price on PA Order Page №1  2  ${s ap_package price for app}
    # Check price of M appPackage
    Check AppPackage price on PA Order Page №1  3  ${m ap_package price for app}
    # Check price of L appPackage
    Check AppPackage price on PA Order Page №1  4  ${l ap_package price for app}


Select AppPackage
    [Arguments]  ${letter}  ${s ap_package price for app}
    ...  ${m ap_package price for app}  ${l ap_package price for app}

    # Choose which button to click
    Click  xpath=//div[contains(@class, "plan-name") and text() = '${letter}']/parent::div/following-sibling::form[contains(@class, "buttons")]/descendant::button[.="Choose package"]
    # Last check price gefore go to billing
    Run Keyword If  '${letter}'=='S'
    ...  Check AppPackage price on PA Order Page №2  ${s ap_package price for app}
    ...  ELSE IF        '${letter}'=='M'
    ...  Check AppPackage price on PA Order Page №2  ${m ap_package price for app}
    ...  ELSE IF        '${letter}'=='L'
    ...  Check AppPackage price on PA Order Page №2  ${l ap_package price for app}
    # Go to billing
    Click  xpath=//button[contains(.,'Order now')]
    Page Should Contain Element  css=.loader


Check AppPackage price on PA Order Page №1
    [Arguments]  ${path}  ${ap_package price for app}
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=  Get Text  xpath=html/body/div[1]/div[2]/div[${path}]/div[1]/div[2]/div[1]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Get expected price from 'price_calculation.robot' file
    Set Expected Price  ${ap_package price for app}
    Comparison of Actual Prices to the Expected


Check AppPackage price on PA Order Page №2
    [Arguments]  ${ap_package price for app}
    Capture Page Screenshot
    # Get actual price from screen
    ${price string}=  Get Text  xpath=html/body/div[1]/div[5]/div[2]
    Set Actual Price by Convert Screen Price Text to Integer  ${price string}
    # Get expected price from 'price_calculation.robot' file
    Set Expected Price  ${ap_package price for app}
    Comparison of Actual Prices to the Expected


Set Actual Price by Convert Screen Price Text to Integer
    [Arguments]  ${price string}
    ${actual price}=  Utils.Correct Actual Price  ${price string}
    Log  ${actual price}
    Set Test Variable  ${test actual price}  ${actual price}


Set Expected Price
    [Arguments]  ${ap_package price}
    ${expected price}=  Set Variable  ${ap_package price}
    Log  ${expected price}
    Set Test Variable  ${test expected price}  ${expected price}


Comparison of Actual Prices to the Expected
    ${is price ok}=  Evaluate  ${test actual price} == ${test expected price}
    Log  ${is price ok}
    Run Keyword If  ${is price ok} == False  Fail
    ...   QA: Comparison of actual prices to the expected is FAIL!!!


Check That Pod is Running
    Wait Until Page Contains Element  jquery=h3:contains(Congratulations!)  15 s
    Sleep  3 s
    # To take correct screenshot if pod isn't running
    Scroll Page To Location    0    2000
    Wait Until Page Contains Element
    ...  jquery=.pod-controls span:contains(running)  15 m


Pod Should Be Unpaid
    Wait Until Element Is Visible  css=.icon.unpaid  15 s

Container Should Be Stoped
    Wait Until Element Is Visible  css=.container-item .stopped  15 s