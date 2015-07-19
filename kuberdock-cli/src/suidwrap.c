#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>'
#include <unistd.h>


int main(int argc, char **argv) {
   char uid[256];
   char * eargv[5];
   snprintf(uid, 256, "%d", getuid());
   eargv[0]=HOOKEXEC;   /* executable path */
   eargv[1]=argv[1];    /* action to fulfil (insert|delete) */
   eargv[2]=argv[2];    /* ipaddress to be restricted */
   eargv[3]=uid;        /* uid */
   eargv[4]=NULL;
   setuid(0);
   execv(eargv[0], eargv);
   return 0;
}