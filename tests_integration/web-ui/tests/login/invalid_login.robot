*** Settings ***
Documentation     A data-driven tests for different cases of invalid login.

Resource          ./resource.robot

Test Template     Login Should Fail


*** Test Cases ***      USER NAME            PASSWORD             MESSAGE
Invalid Username        invalid              ${VALID PASSWORD}
Invalid Password        ${VALID USERNAME}    invalid
Both invalid            invalid              whatever
Empty Username          ${EMPTY}             ${VALID PASSWORD}    Please, enter useraname.
Empty Username (space)  ${SPACE}             ${VALID PASSWORD}    Please, enter useraname.
Empty Password          ${VALID USERNAME}    ${EMPTY}             Please, enter password.
Empty Passwrod (space)  ${VALID USERNAME}    ${SPACE}             Please, enter password.
Both Empty              ${EMPTY}             ${EMPTY}             Please, enter useraname.


*** Keywords ***
Login Should Fail
    [Arguments]    ${username}    ${password}    ${message}=Invalid credentials provided
    Login into the Kuberdock as "${username}" with password "${password}"
    Page Should Contain Only Error Message "${message}"
