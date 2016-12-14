*** Settings ***
Documentation     A resource file for tests with IP pool

Resource          global_resources.robot
Library           Selenium2Library

*** Variables ***
${IP POOL}                192.168.33.224/32
#${EXCLUDE IPs}            None



*** Keywords ***
Add IP pool
    [Arguments]  ${ip pool}=${IP POOL}    ${exclude IPs}=${None}
    Go to IP Pool Page
    Click  css=#create_network
    Input "${ip pool}" in "Subnet" field
    Run Keyword If    ${exclude IPs} is not None    Input "${exclude IPs}" in "Exclude IPs" field
    Click  id=network-add-btn
    Page Should Contain Message "Subnet "${ip pool}" added"


Delete IP Pool
    [Arguments]  ${ip pool}=${IP POOL}
    Go to IP Pool Page
    Click  css=#deleteNetwork[data-original-title="Remove ${ip pool} subnet"]
    Click  jquery=button:contains(Delete)
    Page Should Contain Message "Subnet "${ip pool}" deleted"


Go to IP Pool Page
    Click  jquery=a:contains(Administration)
    Click  jquery=a:contains(IP pool)
    Wait Until Page Contains Element   css=#create_network
