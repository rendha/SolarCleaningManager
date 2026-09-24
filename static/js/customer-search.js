document.addEventListener("DOMContentLoaded", function () {

    console.log("SEARCH JS LOADED");

    /*
     * ==========================================
     * CUSTOMER SEARCH
     * ==========================================
     */

    const customerSelect =
        document.getElementById("id_customer");

    console.log(
        "CUSTOMER SELECT FOUND:",
        customerSelect
    );

    if (customerSelect) {
        createCustomerSearch(customerSelect);
    }


    /*
     * ==========================================
     * SITE SEARCH
     * ==========================================
     *
     * Site options are loaded dynamically when
     * the customer changes.
     *
     * Therefore we watch the <select> for
     * changes to its options.
     */

    const siteSelect =
        document.getElementById("id_site");

    console.log(
        "SITE SELECT FOUND:",
        siteSelect
    );

    if (siteSelect) {

        createSiteSearch(siteSelect);

    }

});


/*
 * =====================================================
 * CUSTOMER SEARCH
 * =====================================================
 */

function createCustomerSearch(select) {

    if (
        select.dataset.customerSearchInitialized ===
        "true"
    ) {
        return;
    }

    select.dataset.customerSearchInitialized =
        "true";


    /*
     * Hide original Django select
     */
    select.style.display = "none";


    /*
     * Wrapper
     */
    const wrapper =
        document.createElement("div");

    wrapper.className =
        "customer-search-wrapper";


    /*
     * Search input
     */
    const input =
        document.createElement("input");

    input.type = "text";

    input.className =
        "form-control customer-search-input";

    input.placeholder =
        "Search customer by name or phone...";

    input.autocomplete = "off";


    /*
     * Dropdown
     */
    const dropdown =
        document.createElement("div");

    dropdown.className =
        "customer-search-results";


    /*
     * Insert wrapper
     */
    select.parentNode.insertBefore(
        wrapper,
        select
    );

    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);
    wrapper.appendChild(select);


    /*
     * Read customers from Django
     */
    function getCustomers() {

        return Array.from(
            select.options
        )
        .filter(function (option) {

            return option.value !== "";

        })
        .map(function (option) {

            return {

                id: option.value,

                name:
                    option.textContent.trim(),

                phone:
                    option.dataset.phone || ""

            };

        });

    }


    /*
     * Existing customer
     */
    if (select.value) {

        const selectedOption =
            select.options[
                select.selectedIndex
            ];

        if (selectedOption) {

            input.value =
                selectedOption.textContent.trim();

        }

    }


    /*
     * SEARCH
     */
    input.addEventListener(
        "input",
        function () {

            const search =
                input.value
                    .trim()
                    .toLowerCase();


            /*
             * Empty
             */
            if (!search) {

                dropdown.innerHTML = "";

                dropdown.style.display =
                    "none";

                return;

            }


            const customers =
                getCustomers();


            /*
             * Search
             */
            const matches =
                customers.filter(
                    function (customer) {

                        return (

                            customer.name
                                .toLowerCase()
                                .includes(search)

                            ||

                            customer.phone
                                .toLowerCase()
                                .includes(search)

                        );

                    }
                );


            dropdown.innerHTML = "";


            /*
             * No results
             */
            if (matches.length === 0) {

                const noResults =
                    document.createElement("div");

                noResults.className =
                    "customer-search-no-results";

                noResults.textContent =
                    "No customers found";

                dropdown.appendChild(
                    noResults
                );

                dropdown.style.display =
                    "block";

                return;

            }


            /*
             * Results
             */
            matches
                .slice(0, 30)
                .forEach(function (customer) {

                    const item =
                        document.createElement("button");

                    item.type = "button";

                    item.className =
                        "customer-search-result";


                    /*
                     * Name
                     */
                    const name =
                        document.createElement("div");

                    name.className =
                        "customer-result-name";

                    name.textContent =
                        customer.name;

                    item.appendChild(name);


                    /*
                     * Phone
                     */
                    if (customer.phone) {

                        const phone =
                            document.createElement("div");

                        phone.className =
                            "customer-result-phone";

                        phone.textContent =
                            customer.phone;

                        item.appendChild(phone);

                    }


                    /*
                     * Prevent blur
                     */
                    item.addEventListener(
                        "mousedown",
                        function (event) {

                            event.preventDefault();

                        }
                    );


                    /*
                     * Select customer
                     */
                    item.addEventListener(
                        "click",
                        function () {

                            select.value =
                                customer.id;

                            input.value =
                                customer.name;

                            dropdown.innerHTML =
                                "";

                            dropdown.style.display =
                                "none";


                            /*
                             * IMPORTANT:
                             * This triggers your existing
                             * loadCustomerSites()
                             */
                            select.dispatchEvent(
                                new Event(
                                    "change",
                                    {
                                        bubbles: true
                                    }
                                )
                            );

                        }
                    );


                    dropdown.appendChild(item);

                });


            dropdown.style.display =
                "block";

        }
    );


    /*
     * Focus
     */
    input.addEventListener(
        "focus",
        function () {

            if (input.value.trim()) {

                input.dispatchEvent(
                    new Event("input")
                );

            }

        }
    );


    /*
     * Blur
     */
    input.addEventListener(
        "blur",
        function () {

            setTimeout(
                function () {

                    dropdown.style.display =
                        "none";

                },
                200
            );

        }
    );

}


/*
 * =====================================================
 * SITE SEARCH
 * =====================================================
 */

function createSiteSearch(select) {

    if (
        select.dataset.siteSearchInitialized ===
        "true"
    ) {
        return;
    }

    select.dataset.siteSearchInitialized =
        "true";


    console.log("CREATING SITE SEARCH");


    /*
     * Hide original select
     */
    select.style.display = "none";


    /*
     * Wrapper
     */
    const wrapper =
        document.createElement("div");

    wrapper.className =
        "customer-search-wrapper";


    /*
     * Search input
     */
    const input =
        document.createElement("input");

    input.type = "text";

    input.className =
        "form-control customer-search-input";

    input.placeholder =
        "Search site or location...";

    input.autocomplete = "off";


    /*
     * Dropdown
     */
    const dropdown =
        document.createElement("div");

    dropdown.className =
        "customer-search-results";


    /*
     * Insert wrapper
     */
    select.parentNode.insertBefore(
        wrapper,
        select
    );

    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);
    wrapper.appendChild(select);


    /*
     * Get current sites from
     * Django select.
     *
     * IMPORTANT:
     * This function runs every time
     * the user searches.
     *
     * Therefore newly loaded AJAX
     * sites are automatically included.
     */
    function getSites() {

        return Array.from(
            select.options
        )
        .filter(function (option) {

            return option.value !== "";

        })
        .map(function (option) {

            return {

                id: option.value,

                name:
                    option.textContent.trim(),

                location:
                    option.dataset.location || "",

                address:
                    option.dataset.address || "",

                solarKw:
                    option.dataset.solarKw || ""

            };

        });

    }


    /*
     * When AJAX changes the site options,
     * update the visible search box.
     */
    const observer =
        new MutationObserver(
            function () {

                /*
                 * If a site is selected,
                 * show it in the search box.
                 */
                if (select.value) {

                    const selectedOption =
                        select.options[
                            select.selectedIndex
                        ];

                    if (selectedOption) {

                        input.value =
                            selectedOption.textContent
                                .trim();

                    }

                }

            }
        );


    observer.observe(
        select,
        {
            childList: true
        }
    );


    /*
     * Existing selected site
     */
    if (select.value) {

        const selectedOption =
            select.options[
                select.selectedIndex
            ];

        if (selectedOption) {

            input.value =
                selectedOption.textContent.trim();

        }

    }


    /*
     * ==========================================
     * SITE SEARCH INPUT
     * ==========================================
     */

    input.addEventListener(
        "input",
        function () {

            /*
             * IMPORTANT:
             *
             * We use the ENTIRE text entered.
             *
             * "ka"
             *
             * searches for "ka".
             *
             * It does NOT search for "k"
             * and then "a" separately.
             */
            const search =
                input.value
                    .trim()
                    .toLowerCase();


            /*
             * Empty search
             */
            if (!search) {

                dropdown.innerHTML =
                    "";

                dropdown.style.display =
                    "none";

                return;

            }


            const sites =
                getSites();


            /*
             * Search site name,
             * location and address.
             */
            const matches =
                sites.filter(
                    function (site) {

                        return (

                            site.name
                                .toLowerCase()
                                .includes(search)

                            ||

                            site.location
                                .toLowerCase()
                                .includes(search)

                            ||

                            site.address
                                .toLowerCase()
                                .includes(search)

                        );

                    }
                );


            /*
             * Clear results
             */
            dropdown.innerHTML =
                "";


            /*
             * No results
             */
            if (matches.length === 0) {

                const noResults =
                    document.createElement("div");

                noResults.className =
                    "customer-search-no-results";

                noResults.textContent =
                    "No sites found";

                dropdown.appendChild(
                    noResults
                );

                dropdown.style.display =
                    "block";

                return;

            }


            /*
             * Show results
             */
            matches
                .slice(0, 30)
                .forEach(function (site) {

                    const item =
                        document.createElement("button");

                    item.type = "button";

                    item.className =
                        "customer-search-result";


                    /*
                     * Site name
                     */
                    const name =
                        document.createElement("div");

                    name.className =
                        "customer-result-name";

                    name.textContent =
                        site.name;

                    item.appendChild(name);


                    /*
                     * Location
                     */
                    if (site.location) {

                        const location =
                            document.createElement("div");

                        location.className =
                            "customer-result-phone";

                        location.textContent =
                            site.location;

                        item.appendChild(
                            location
                        );

                    }


                    /*
                     * Address
                     */
                    if (
                        site.address &&
                        site.address !== site.location
                    ) {

                        const address =
                            document.createElement("div");

                        address.className =
                            "customer-result-phone";

                        address.textContent =
                            site.address;

                        item.appendChild(
                            address
                        );

                    }


                    /*
                     * Prevent input blur
                     */
                    item.addEventListener(
                        "mousedown",
                        function (event) {

                            event.preventDefault();

                        }
                    );


                    /*
                     * SELECT SITE
                     */
                    item.addEventListener(
                        "click",
                        function () {

                            /*
                             * Set Django select
                             */
                            select.value =
                                site.id;


                            /*
                             * Show selected site
                             */
                            input.value =
                                site.name;


                            /*
                             * Hide results
                             */
                            dropdown.innerHTML =
                                "";

                            dropdown.style.display =
                                "none";


                            /*
                             * IMPORTANT:
                             *
                             * Your existing schedule_form.html
                             * listens for this change and
                             * fills:
                             *
                             * Location
                             * Address
                             * Site info
                             */
                            select.dispatchEvent(
                                new Event(
                                    "change",
                                    {
                                        bubbles: true
                                    }
                                )
                            );

                        }
                    );


                    dropdown.appendChild(item);

                });


            dropdown.style.display =
                "block";

        }
    );


    /*
     * Focus
     */
    input.addEventListener(
        "focus",
        function () {

            if (input.value.trim()) {

                input.dispatchEvent(
                    new Event("input")
                );

            }

        }
    );


    /*
     * Blur
     */
    input.addEventListener(
        "blur",
        function () {

            setTimeout(
                function () {

                    dropdown.style.display =
                        "none";

                },
                200
            );

        }
    );

}
