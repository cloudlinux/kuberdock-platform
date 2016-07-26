*** Settings ***
Documentation     Different scenarios of valid login.

Resource          ./resource.robot


*** Test Cases ***
Valid Login
    Login into the Kuberdock as "${VALID USERNAME}" with password "${VALID PASSWORD}"
    Nodes View Should Be Open
    [Teardown]    Logout

Trim Whitespace In Username And Password
    Login into the Kuberdock as " \ ${VALID USERNAME} \ " with password " \ ${VALID PASSWORD} \ "
    Nodes View Should Be Open
    [Teardown]    Logout
