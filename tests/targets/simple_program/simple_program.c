#include <stdio.h>
#include <stdbool.h>
#include <string.h>

int main()
{
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    char buffer[128];

    while (true) {
        if (!fgets(buffer, 128, stdin))
            break;

        if (!strcmp(buffer, "hello\n"))
            puts("world");
        else if (!strcmp(buffer, "hola\n"))
            puts("mundo");
        else if (!strcmp(buffer, "exit\n"))
            break;
        else
            puts("what?");

    }

    return 0;
}
