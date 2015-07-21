#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>


int main(int argc, char **argv) {
   char uid[256];
   char * eargv[9];
   snprintf(uid, 256, "%d", getuid());
   eargv[0]=HOOKEXEC;   /* executable path */
   eargv[1]="--token";
   eargv[2]=argv[1];    /* token */
   eargv[3]="kubectl";
   eargv[4]="postprocess";
   eargv[5]=argv[2];    /* pod name */
   eargv[6]="--uid";
   eargv[7]=uid;        /* uid */
   eargv[8]=NULL;
   setuid(0);
   execv(eargv[0], eargv);
   return 0;
}