    # SigmaOS-sticky-notes

    Sticky notes applet

    Part of the **SigmaOS** sovereign operating-system ecosystem — a multi-repository
    distribution modelled on Linux Mint and Omarchy Linux. See the parent
    [`SigmaOS`](https://github.com/AaryanSinghChauhan09/SigmaOS) repository for the
    full component index.

    ## Upstream inspirations
    - https://github.com/linuxmint/sticky

    ## Design principles applied
    - **Encapsulation**
- **Least Astonishment**
- **Fail-Fast**
- **KISS**
- **DRY**
- **Deterministic Testing**

    ## Usage
    Verbs: `add, list, edit, pin, search`

    ```
    $ sigma-sticky add "buy milk"
added note 1
$ sigma-sticky add "ship SigmaOS" --pin
$ sigma-sticky list
$ sigma-sticky edit 1 --text "buy oat milk"
$ sigma-sticky search milk

    ```

    ## Build & test
    ```
    make build
    make test
    ```

    ## Licence
    GNU General Public License v3.0 (FOSS).
