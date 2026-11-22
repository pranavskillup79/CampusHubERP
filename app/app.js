"use strict";

const element = (id) => document.getElementById(id);
const create = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
};
const personFields = [
    ["name", "Name", "text"], ["age", "Age", "integer"],
    ["email", "Email", "email"], ["department", "Department", "text"],
];
const pages = {
    students: { title: "Students", singular: "student", id: "student_id", idLabel: "Student ID", name: "name",
        fields: personFields, columns: [["student_id", "Student ID"], ["name", "Name"],
            ["age", "Age"], ["email", "Email"], ["department", "Department"]],
        search: ["name", "student_id"], departments: true, cascade: true },
    faculty: { title: "Faculty", singular: "faculty member", id: "faculty_id", idLabel: "Faculty ID", name: "name",
        fields: personFields, columns: [["faculty_id", "Faculty ID"], ["name", "Name"],
            ["age", "Age"], ["email", "Email"], ["department", "Department"]],
        search: ["name", "faculty_id"], departments: true },
    courses: { title: "Courses", singular: "course", id: "course_code", idLabel: "Course code", name: "course_name",
        fields: [["course_name", "Course name", "text"], ["credits", "Credits", "integer"]],
        columns: [["course_code", "Course code"], ["course_name", "Course name"], ["credits", "Credits"]],
        search: ["course_name", "course_code"], searchHint: "Course name or code", cascade: true },
    enrollments: { title: "Enrollments", singular: "enrollment", id: "id", name: "student_name",
        displayId: "student_id",
        addFields: [["student_id", "Student", "select"], ["course_code", "Course", "select"]],
        columns: [["student_name", "Student"], ["student_id", "Student ID"], ["course_name", "Course"],
            ["course_code", "Course code"], ["enrolled_on", "Enrolled on"]],
        search: ["student_name", "student_id", "course_name", "course_code"], searchHint: "Student or course",
        removeLabel: "Remove" },
    optimizer: { title: "Study Time Optimizer" },
};
const state = { page: "", rows: [], loaded: false, loading: false, error: "", request: 0,
    sortKey: "", sortDirection: "ascending", recordPage: 1 };
const recordsPerPage = 10;
const recordCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
const enrollmentDate = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const numericColumns = new Set(["age", "credits"]);
const editorHints = { age: "Whole number, 16–80.", credits: "Whole number, 1 or more." };
// FastAPI string errors fall back to the general notice when the wording does not match.
const editorErrorFields = [["email", "email"], ["age", "age"], ["credits", "credits"],
    ["course name", "course_name"], ["department", "department"], ["name", "name"]];
const plannerErrorFields = [["Available hours", "total"], ["Course A minimum", "minimum_a"],
    ["Course A maximum", "maximum_a"], ["Course A priority", "priority_a"],
    ["Course B minimum", "minimum_b"], ["Course B maximum", "maximum_b"], ["Course B priority", "priority_b"]];
const recordViews = new Map();
const dialog = element("editor");
const editorForm = element("editor-form");
let editing = null;
let writing = false;
let toastTimer;
let highlightedRecord = null;
let highlightTimer;

class ApiError extends Error {
    constructor(status, detail) {
        super(typeof detail === "string" ? detail : "Check the highlighted fields and try again.");
        this.status = status;
        this.detail = detail;
    }
}

async function api(path, method = "GET", data = undefined) {
    let response;
    try {
        response = await fetch(path, {
            method, headers: data === undefined ? {} : { "Content-Type": "application/json" },
            body: data === undefined ? undefined : JSON.stringify(data),
            cache: "no-store",
        });
    } catch {
        throw new Error("Can’t reach the CampusHub server. Check your connection, then try again.");
    }
    const result = await response.json().catch(() => null);
    if (!response.ok) {
        throw new ApiError(response.status, result?.detail ?? "The request failed. Please try again.");
    }
    return result;
}

function notice(text = "", error = false, target = element("notice")) {
    target.classList.toggle("error", error);
    target.textContent = text && error ? "Error: " + text : text;
    if (target.id !== "notice") return;
    clearTimeout(toastTimer);
    const toast = element("record-toast");
    toast.classList.toggle("active", Boolean(text));
    toast.classList.toggle("error", error);
    element("dismiss-notice").hidden = !text;
    if (text && !error) toastTimer = setTimeout(clearSuccessToast, 6000);
}

function clearSuccessToast() {
    if (document.activeElement !== element("dismiss-notice")) notice();
}

function connection(status) {
    const text = element("connection-text");
    if (text.parentElement.dataset.state === status) return;
    text.parentElement.dataset.state = status;
    const [icon, message] = {
        online: ["✓", "Records connected"],
        loading: ["…", "Connecting to records…"],
        error: ["!", "Could not load records"],
    }[status];
    element("connection-icon").textContent = icon;
    text.textContent = message;
}

function option(select, value, label) {
    const item = create("option", label);
    item.value = value;
    select.append(item);
}

function loadingLabel(text) {
    const label = create("span", "", "loading-label");
    const dots = create("span", "", "loading-dots");
    dots.setAttribute("aria-hidden", "true");
    dots.append(create("i"), create("i"), create("i"));
    label.append(document.createTextNode(text), dots);
    return label;
}

function buildDepartments(previous = element("department").value) {
    const select = element("department");
    select.replaceChildren();
    option(select, "", "All departments");
    const unique = [...new Set(state.rows.map((row) => row.department).filter(Boolean))];
    unique.sort((left, right) => left.localeCompare(right));
    for (const department of unique) option(select, department, department);
    if (unique.includes(previous)) select.value = previous;
}

function rowButton(action, row, config) {
    const label = action === "edit" ? "Edit" : config.removeLabel || "Delete";
    const button = create("button", label, "button quiet" + (action === "edit" ? "" : " danger-text"));
    button.type = "button";
    button.dataset.recordAction = action;
    button.dataset.recordId = row[config.id];
    const target = row[config.name] ?? row[config.id];
    button.setAttribute("aria-label", label + " " + (config.removeLabel ? target + " from " + row.course_name : target));
    button.addEventListener("click", () => openEditor(action, row, button));
    return button;
}

function findRowButton(action, id) {
    return [...element("table-body").querySelectorAll("[data-record-action]")].find(
        (button) => button.dataset.recordAction === action && button.dataset.recordId === id,
    );
}

function recordCell(record, key, label, config) {
    const cell = create("td");
    cell.setAttribute("role", "cell");
    const value = record[key] ?? "";
    const caption = create("span", label, "cell-label");
    caption.setAttribute("aria-hidden", "true");
    const date = key === "enrolled_on" && value ? new Date(value) : null;
    const content = date && !Number.isNaN(date.valueOf()) ? create("time", enrollmentDate.format(date))
        : create("span", value);
    if (content.tagName === "TIME") content.dateTime = value;
    cell.append(caption, content);
    if (numericColumns.has(key)) cell.classList.add("numeric-cell");
    if (key === config.name) cell.classList.add("record-name");
    if (key === (config.displayId ?? config.id)) cell.classList.add("record-id");
    if (key === "email") cell.classList.add("record-email");
    return cell;
}

function setSort(key, direction = "ascending") {
    state.sortKey = key;
    state.sortDirection = direction;
    restartRecordList();
}

function buildRecordSort(config) {
    const options = element("record-sort");
    options.replaceChildren();
    option(options, "", "Default order");
    const head = create("tr");
    head.setAttribute("role", "row");
    for (const [key, label] of config.columns) {
        const cell = create("th");
        cell.scope = "col";
        cell.setAttribute("role", "columnheader");
        if (numericColumns.has(key)) cell.classList.add("numeric-cell");
        const button = create("button", label, "sort-button");
        const indicator = create("span", "↕", "sort-indicator");
        indicator.setAttribute("aria-hidden", "true");
        button.type = "button";
        button.append(indicator);
        button.title = "Sort by " + label;
        button.addEventListener("click", () => {
            if (state.sortKey !== key) setSort(key);
            else if (state.sortDirection === "ascending") setSort(key, "descending");
            else setSort("");
        });
        cell.dataset.sortKey = key;
        cell.append(button, create("span", label, "compact-column-label"));
        head.append(cell);
        const numeric = key === "age" || key === "credits";
        const [ascending, descending] = key === "enrolled_on" ? ["Oldest first", "Newest first"]
            : numeric ? ["Low to high", "High to low"] : ["A to Z", "Z to A"];
        option(options, key + ":ascending", label + " · " + ascending);
        option(options, key + ":descending", label + " · " + descending);
    }
    const actions = create("th", "Actions");
    actions.scope = "col";
    actions.setAttribute("role", "columnheader");
    head.append(actions);
    element("table-head").replaceChildren(head);
}

function updateRecordSort() {
    for (const cell of element("table-head").querySelectorAll("[data-sort-key]")) {
        const sorted = cell.dataset.sortKey === state.sortKey;
        if (sorted) cell.setAttribute("aria-sort", state.sortDirection);
        else cell.removeAttribute("aria-sort");
        const arrow = state.sortDirection === "ascending" ? "↑" : "↓";
        cell.querySelector(".sort-indicator").textContent = sorted ? arrow : "↕";
    }
    element("record-sort").value = state.sortKey ? state.sortKey + ":" + state.sortDirection : "";
}

function updateRecordPagination(matches, first, pageCount, filtered) {
    const total = state.rows.length;
    const noun = total === 1 ? " record" : " records";
    let count = filtered ? matches + " of " + total + noun : total + noun;
    if (pageCount > 1) {
        const end = Math.min(first + recordsPerPage, matches);
        count = (first + 1) + "–" + end + " of " + matches + " records";
        if (filtered) count += " (" + total + " total)";
    }
    const countLabel = element("table-count");
    const status = state.loaded ? count : "";
    if (countLabel.textContent !== status) countLabel.textContent = status;
    element("record-pagination").hidden = pageCount < 2;
    element("record-page").textContent = "Page " + state.recordPage + " of " + pageCount;
    element("previous-page").disabled = state.recordPage === 1;
    element("next-page").disabled = state.recordPage >= pageCount;
}

function renderTable(revealId) {
    const config = pages[state.page];
    const table = element("table-body");
    const active = document.activeElement;
    const activeAction = active?.dataset.recordAction;
    const query = element("search").value.trim().toLowerCase();
    const department = config.departments ? element("department").value : "";
    const filtered = Boolean(query || department);
    const filterCount = Number(Boolean(department)) + Number(Boolean(state.sortKey));
    const badge = element("filter-count");
    badge.textContent = filterCount ? "(" + filterCount + " active)" : "";
    badge.hidden = filterCount === 0;
    element("clear-filters").hidden = !filtered;
    const rows = state.rows.filter((row) => (!department || row.department === department)
        && config.search.some((field) => String(row[field] ?? "").toLowerCase().includes(query)));
    const { sortKey, sortDirection } = state;
    if (sortKey) {
        const direction = sortDirection === "ascending" ? 1 : -1;
        rows.sort((left, right) => direction * recordCollator.compare(left[sortKey] ?? "", right[sortKey] ?? ""));
    }
    const pageCount = Math.max(1, Math.ceil(rows.length / recordsPerPage));
    if (revealId != null) {
        const index = rows.findIndex((row) => row[config.id] === revealId);
        if (index !== -1) state.recordPage = Math.floor(index / recordsPerPage) + 1;
    }
    if (state.loaded) state.recordPage = Math.min(state.recordPage, pageCount);
    const first = (state.recordPage - 1) * recordsPerPage;
    const contents = document.createDocumentFragment();
    if (!rows.length) {
        const row = create("tr");
        row.setAttribute("role", "row");
        let message = "No " + config.title.toLowerCase() + " yet.";
        if (state.loading && !state.loaded) message = "Loading " + config.title.toLowerCase() + "…";
        else if (state.error && !state.loaded) message = state.error;
        else if (filtered) message = "No matching " + config.title.toLowerCase() + ".";
        const cell = create("td", "", "table-state");
        cell.setAttribute("role", "cell");
        cell.append(state.loading && !state.loaded ? loadingLabel(message) : document.createTextNode(message));
        if (state.error && !state.loaded) {
            const retry = create("button", "Try again", "button secondary");
            retry.type = "button";
            retry.id = "retry-records";
            retry.addEventListener("click", () => loadRecords(true));
            const action = create("div");
            action.append(retry);
            cell.append(action);
        } else if (state.loaded && filtered) {
            cell.append(create("span", "Try a different search or clear your filters.", "table-state-hint"));
        } else if (state.loaded) {
            const add = create("button", "Add " + config.singular, "button secondary");
            add.type = "button";
            add.addEventListener("click", () => openEditor("add", null, add));
            const action = create("div");
            action.append(add);
            cell.append(action);
        }
        cell.colSpan = config.columns.length + 1;
        row.append(cell);
        contents.append(row);
    }
    for (const record of rows.slice(first, first + recordsPerPage)) {
        const row = create("tr", "", "record-row");
        row.setAttribute("role", "row");
        if (highlightedRecord?.page === state.page && highlightedRecord.id === record[config.id]) {
            row.classList.add("record-highlight");
        }
        for (const [key, label] of config.columns) row.append(recordCell(record, key, label, config));
        const cell = create("td", "", "action-cell");
        cell.setAttribute("role", "cell");
        const actions = create("div", "", "row-actions");
        if (config.fields) actions.append(rowButton("edit", record, config));
        actions.append(rowButton("delete", record, config));
        cell.append(actions);
        row.append(cell);
        contents.append(row);
    }
    table.replaceChildren(contents);
    if (activeAction) (findRowButton(activeAction, active.dataset.recordId) ?? element("add-record")).focus();
    updateRecordSort();
    updateRecordPagination(rows.length, first, pageCount, filtered);
    element("records").setAttribute("aria-busy", String(state.loading));
    syncRecordScroll();
}

const recordScroll = element("record-scroll");
function syncRecordScroll() {
    recordScroll.tabIndex = recordScroll.scrollWidth > recordScroll.clientWidth ? 0 : -1;
}
new ResizeObserver(syncRecordScroll).observe(recordScroll);

function restartRecordList() {
    state.recordPage = 1;
    renderTable();
}

function changeRecordPage(offset) {
    state.recordPage += offset;
    renderTable();
    recordScroll.focus({ preventScroll: true });
    recordScroll.scrollIntoView({ block: "start", inline: "nearest" });
}

async function loadRecords(focusResult = false, revealId = null) {
    const page = state.page;
    const request = ++state.request;
    state.loading = true;
    state.error = "";
    element("refresh").disabled = true;
    element("refresh").replaceChildren(loadingLabel("Refreshing…"));
    if (!state.loaded) connection("loading");
    renderTable();
    if (focusResult) recordScroll.focus({ preventScroll: true });
    try {
        const data = await api("/" + page);
        if (request !== state.request) return;
        if (!Array.isArray(data)) throw new Error("The server returned an unreadable record list.");
        const department = state.loaded ? element("department").value : recordViews.get(page)?.department;
        state.rows = data;
        state.loaded = true;
        if (pages[page].departments) buildDepartments(department);
        connection("online");
    } catch (error) {
        if (request !== state.request) return;
        state.error = error.message;
        if (state.loaded) notice("Refresh failed: " + error.message, true);
        connection("error");
    } finally {
        if (request === state.request) {
            state.loading = false;
            element("refresh").disabled = false;
            element("refresh").textContent = "Refresh";
            renderTable(state.error ? null : revealId);
            if (focusResult && document.activeElement === recordScroll) {
                element("retry-records")?.focus();
            }
        }
    }
}

function showPage(event) {
    const key = location.hash.slice(1);
    if (key === "workspace" && state.page) return;
    const page = Object.hasOwn(pages, key) ? key : "students";
    if (state.page === page) return;
    if (state.loaded) {
        const { sortKey, sortDirection, recordPage } = state;
        recordViews.set(state.page, { sortKey, sortDirection, recordPage,
            search: element("search").value, department: element("department").value });
    }
    const config = pages[page];
    const view = recordViews.get(page);
    Object.assign(state, { page, rows: [], loaded: false, loading: false, error: "",
        sortKey: view?.sortKey ?? "", sortDirection: view?.sortDirection ?? "ascending",
        recordPage: view?.recordPage ?? 1 });
    state.request += 1;
    notice();
    document.title = config.title + " · CampusHub ERP";
    element("page-title").textContent = config.title;
    for (const link of document.querySelectorAll(".workspace-links [data-page]")) {
        if (link.dataset.page === page) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    }
    const planning = page === "optimizer";
    element("records").hidden = planning;
    element("optimizer").hidden = !planning;
    element("add-record").hidden = planning;
    if (event) {
        window.scrollTo(0, 0);
        element("page-title").focus({ preventScroll: true });
    }
    if (planning) {
        loadOptimizerChoices();
        return;
    }
    element("add-record").lastChild.textContent = " Add " + config.singular;
    element("department-control").hidden = !config.departments;
    element("search").value = view?.search ?? "";
    element("search").placeholder = config.searchHint || "Name or ID";
    buildDepartments("");
    buildRecordSort(config);
    loadRecords();
}

function editorField(key, label, type, value = "", choices = []) {
    const field = create("div", "", "control");
    const input = create(type === "select" ? "select" : "input");
    input.id = "edit-" + key;
    input.name = key;
    input.setAttribute("autocomplete", "off");
    const caption = create("label", label);
    caption.htmlFor = input.id;
    if (type === "select") {
        option(input, "", "Select " + label.toLowerCase());
        for (const [id, text] of choices) option(input, id, text);
    } else {
        input.type = type === "integer" ? "number" : type === "readonly" ? "text" : type;
        if (type === "integer") input.step = "1";
        input.readOnly = type === "readonly";
    }
    input.value = value ?? "";
    input.required = type !== "readonly";
    const error = create("span", "", "field-error");
    error.id = input.id + "-error";
    error.hidden = true;
    const hint = editorHints[key] && create("span", editorHints[key], "field-hint");
    if (hint) hint.id = input.id + "-hint";
    input.setAttribute("aria-describedby", hint ? hint.id + " " + error.id : error.id);
    input.addEventListener("input", () => setFieldError(key, ""));
    field.append(caption, input);
    if (hint) field.append(hint);
    field.append(error);
    return field;
}

function setFieldError(key, message) {
    const input = element("edit-" + key);
    if (!input) return false;
    const error = element(input.id + "-error");
    input.setAttribute("aria-invalid", String(Boolean(message)));
    error.textContent = message ? "Error: " + message : "";
    error.hidden = !message;
    return true;
}

function showEditorErrors(error) {
    let general = error.message;
    if (Array.isArray(error.detail)) {
        const unmatched = [];
        for (const detail of error.detail) {
            if (!setFieldError(detail.loc?.at(-1), detail.msg)) unmatched.push(detail.msg);
        }
        general = unmatched.join(" ");
    } else if (error.status === 422) {
        const text = error.message.toLowerCase();
        const field = editorErrorFields
            .find(([phrase]) => new RegExp("\\b" + phrase + "\\b").test(text));
        if (field && setFieldError(field[1], error.message)) general = "";
    }
    if (error.status === 409) general = "This student is already enrolled in that course.";
    notice(general, true, element("editor-error"));
    editorForm.querySelector('[aria-invalid="true"]')?.focus();
}

function setWriting(value) {
    writing = value;
    for (const control of editorForm.querySelectorAll("button, input, select")) control.disabled = value;
    if (value) element("save-record").replaceChildren(loadingLabel("Working…"));
    else element("save-record").textContent = editing.label;
}

function openEditor(mode, row, opener) {
    if (dialog.open) return;
    const page = state.page;
    const config = pages[page];
    const fields = element("editor-fields");
    const save = element("save-record");
    editing = { mode, row, opener, config, page, label: "Save changes" };
    notice("", false, element("editor-error"));
    element("editor-requirements").hidden = mode === "delete";
    fields.replaceChildren();
    save.hidden = false;
    element("editor-title").textContent = mode === "delete" ? (config.removeLabel ?? "Delete") + " " + config.singular
        : (mode === "edit" ? "Edit " : "Add ") + config.singular;
    save.classList.toggle("danger-button", mode === "delete");
    if (mode === "delete") {
        editing.label = config.removeLabel ?? "Delete " + config.singular;
        const name = row[config.name] ?? row[config.id];
        const target = config.addFields ? name + " (" + row.student_id + ") from "
            + row.course_name + " (" + row.course_code + ")" : config.singular + " " + name + " (" + row[config.id] + ")";
        fields.append(create("p", (config.removeLabel ?? "Delete") + " " + target + "?"));
        fields.append(create("p", "This can’t be undone."));
        if (config.cascade) {
            const impact = page === "students" ? "All course enrollments for this student will also be removed."
                : "All student enrollments in this course will also be removed.";
            fields.append(create("p", impact));
        }
    } else if (config.fields) {
        if (row) fields.append(editorField("record_id", config.idLabel || "Record ID", "readonly", row[config.id]));
        for (const [key, label, type] of config.fields) fields.append(editorField(key, label, type, row?.[key]));
        if (mode === "add") editing.label = "Add " + config.singular;
    } else {
        editing.label = "Add enrollment";
        const loading = create("p");
        loading.append(loadingLabel("Loading students and courses…"));
        fields.append(loading);
        save.disabled = true;
    }
    save.textContent = editing.label;
    dialog.showModal();
    if (mode === "delete") element("cancel-editor").focus();
    else fields.querySelector("input:not([readonly]), select")?.focus();
    if (mode === "add" && config.addFields) loadEnrollmentChoices(editing);
}

function enrollmentPicker(key, label, choices) {
    const field = editorField(key, label, "select", "", choices);
    if (choices.length <= 50) return field;
    const search = create("input");
    search.type = "search";
    search.autocomplete = "off";
    search.placeholder = "Search by name or ID";
    const searchLabel = create("label", "Find " + label.toLowerCase(), "control");
    searchLabel.append(search);
    const select = field.querySelector("select");
    search.setAttribute("aria-controls", select.id);
    search.addEventListener("input", () => {
        const query = search.value.trim().toLowerCase();
        const matches = choices.filter(([, name]) => name.toLowerCase().includes(query));
        replaceOptions(select, matches, matches.length ? "Select " + label.toLowerCase() : "No matches");
    });
    const group = create("div", "", "enrollment-picker");
    group.append(searchLabel, field);
    return group;
}

async function loadEnrollmentChoices(current) {
    try {
        const [students, courses] = await Promise.all([api("/students"), api("/courses")]);
        if (!dialog.open || editing !== current) return;
        const fields = element("editor-fields");
        fields.replaceChildren(
            enrollmentPicker("student_id", "Student",
                students.map((student) => [student.student_id, student.name + " (" + student.student_id + ")"])),
            enrollmentPicker("course_code", "Course",
                courses.map((course) => [course.course_code, course.course_name + " (" + course.course_code + ")"])),
        );
        if (!students.length || !courses.length) {
            notice("Add at least one student and one course before enrolling.", true, element("editor-error"));
        } else {
            element("save-record").disabled = false;
            fields.querySelector("input, select")?.focus();
        }
    } catch (error) {
        if (dialog.open && editing === current) {
            element("editor-fields").replaceChildren();
            showEditorErrors(error);
        }
    }
}

async function saveEditor(event) {
    event.preventDefault();
    if (!editing || writing || element("save-record").disabled) return;
    const { mode, row, config, page } = editing;
    notice("", false, element("editor-error"));
    const body = {};
    let invalid = false;
    if (mode !== "delete") {
        for (const [key, label, type] of config.fields ?? config.addFields) {
            const input = element("edit-" + key);
            setFieldError(key, "");
            const text = input.value.trim();
            if (row && text === String(row[key] ?? "")) continue;
            if (!text || (type === "integer" && !/^-?\d+$/.test(text))) {
                setFieldError(key, type === "integer" && text ? label + " must be a whole number." : label + " is required.");
                invalid = true;
                continue;
            }
            const value = type === "integer" ? Number(text) : text;
            if (type === "integer" && !Number.isSafeInteger(value)) {
                setFieldError(key, label + " is too large.");
                invalid = true;
            } else if (!row || row[key] !== value) {
                body[key] = value;
            }
        }
        if (invalid) {
            editorForm.querySelector('[aria-invalid="true"]')?.focus();
            return;
        }
        if (mode === "edit" && !Object.keys(body).length) {
            notice("No changes to save.", false, element("editor-error"));
            return;
        }
    }
    const path = "/" + page + (row ? "/" + encodeURIComponent(row[config.id]) : "");
    const method = mode === "delete" ? "DELETE" : mode === "edit" ? "PUT" : "POST";
    setWriting(true);
    try {
        const response = await api(path, method, mode === "delete" ? undefined : body);
        setWriting(false);
        dialog.close();
        if (state.page !== page) return;
        const record = mode === "delete" ? row : response;
        const name = record?.[config.name];
        const id = record?.[config.id];
        const label = config.singular[0].toUpperCase() + config.singular.slice(1);
        const course = config.addFields && record?.course_name ? " · " + record.course_name : "";
        const action = mode === "delete" ? (config.removeLabel ? "removed" : "deleted") : mode === "edit" ? "updated" : "added";
        const target = name && id ? " " + name + course + " (" + id + ")" : "";
        notice(label + target + " " + action + ".");
        const highlight = mode !== "delete" && id != null ? { page, id } : null;
        clearTimeout(highlightTimer);
        highlightedRecord = highlight;
        await loadRecords(false, highlight?.id);
        if (highlight && highlightedRecord === highlight) {
            highlightTimer = setTimeout(() => {
                highlightedRecord = null;
                element("table-body").querySelector(".record-highlight")?.classList.remove("record-highlight");
            }, 2000);
        }
    } catch (error) {
        setWriting(false);
        showEditorErrors(error);
    }
}

const optimizerForm = element("optimizer-form");
const planStudent = element("plan-student");
const planCourseA = element("plan-course-a");
const planCourseB = element("plan-course-b");
let planEnrollments = [];
let planningRequest = false;
let loadingChoices = false;

function replaceOptions(select, records, placeholder) {
    const previous = select.value;
    select.replaceChildren();
    option(select, "", placeholder);
    for (const [id, text] of records) option(select, id, text);
    if (records.some(([id]) => id === previous)) select.value = previous;
}

function representPlan(data = null, names = null) {
    const objective = element("plan-objective");
    const constraints = element("plan-constraints");
    if (!data) {
        objective.textContent = "Maximize priority A × x + priority B × y.";
        constraints.textContent = "x + y ≤ available hours. Each course must stay between its minimum and maximum hours.";
        return;
    }
    objective.textContent = "Maximize " + data.priority_a + "x + " + data.priority_b
        + "y, where x is hours for " + names[0] + " and y is hours for " + names[1] + ".";
    constraints.textContent = "Constraints: x + y ≤ " + data.total + ", " + data.minimum_a
        + " ≤ x ≤ " + data.maximum_a + ", " + data.minimum_b + " ≤ y ≤ " + data.maximum_b + ".";
}

function clearPlanFeedback() {
    element("plan-result").hidden = true;
    element("corner-results").hidden = true;
    if (element("retry-options").hidden) notice("", false, element("optimizer-notice"));
    for (const input of optimizerForm.querySelectorAll('[aria-invalid="true"]')) {
        input.removeAttribute("aria-invalid");
    }
    for (const error of optimizerForm.querySelectorAll(".field-error")) {
        error.hidden = true;
        error.textContent = "";
    }
    representPlan();
}

// Keep error descriptions separate from the labels read by assistive technology.
function markPlanField(name, message) {
    const input = optimizerForm.elements.namedItem(name);
    if (!input) return false;
    const label = input.parentElement;
    let error = label.querySelector(".field-error");
    if (!error) {
        const caption = create("span", label.firstChild.textContent.trim());
        caption.id = "plan-" + name + "-label";
        label.firstChild.replaceWith(caption);
        input.setAttribute("aria-labelledby", caption.id);
        error = create("span", "", "field-error");
        error.id = "plan-" + name + "-error";
        label.append(error);
        const description = input.getAttribute("aria-describedby");
        input.setAttribute("aria-describedby", description ? description + " " + error.id : error.id);
    }
    error.textContent = "Error: " + message;
    error.hidden = false;
    input.setAttribute("aria-invalid", "true");
    return true;
}

function syncCourseOptions() {
    for (const [select, other] of [[planCourseA, planCourseB], [planCourseB, planCourseA]]) {
        for (const item of select.options) item.disabled = Boolean(item.value && item.value === other.value);
    }
}

function updateCourseChoices() {
    const rows = planEnrollments.filter((row) => row.student_id === planStudent.value);
    rows.sort((left, right) => left.course_name.localeCompare(right.course_name)
        || left.course_code.localeCompare(right.course_code));
    const options = rows.map((row) => [row.course_code, row.course_name + " (" + row.course_code + ")"]);
    for (const select of [planCourseA, planCourseB]) {
        replaceOptions(select, options, "Select enrolled course");
        select.disabled = !options.length || planningRequest;
    }
    if (options.length === 2) {
        for (const [select, other] of [[planCourseA, planCourseB], [planCourseB, planCourseA]]) {
            if (!select.value) select.value = options.find(([id]) => id !== other.value)[0];
        }
    }
    syncCourseOptions();
    const hint = element("plan-hint");
    hint.textContent = !planStudent.value ? "Select a student to see their enrolled courses." : "Choose two different courses.";
    if (planStudent.value && rows.length < 2) {
        const link = create("a", "Enrollments");
        link.href = "#enrollments";
        hint.replaceChildren("This student needs at least two courses. Add courses in ", link, ".");
    }
    element("calculate-plan").disabled = loadingChoices || planningRequest || options.length < 2;
    clearPlanFeedback();
}

async function loadOptimizerChoices(focusResult = false) {
    const request = ++state.request;
    loadingChoices = true;
    element("retry-options").hidden = true;
    clearPlanFeedback();
    element("reload-options").disabled = true;
    element("reload-options").replaceChildren(loadingLabel("Refreshing…"));
    element("calculate-plan").disabled = true;
    element("plan-hint").replaceChildren(loadingLabel("Loading students and enrollments…"));
    try {
        const [students, enrollments] = await Promise.all([api("/students"), api("/enrollments")]);
        if (request !== state.request) return;
        planEnrollments = enrollments;
        replaceOptions(planStudent, students.map((student) => [
            student.student_id, student.name + " (" + student.student_id + ")",
        ]), "Select student");
        connection("online");
        loadingChoices = false;
        updateCourseChoices();
        if (!students.length) element("plan-hint").textContent = "Add students and enroll them before planning.";
        if (focusResult && document.activeElement === document.body) planStudent.focus();
    } catch (error) {
        if (request !== state.request) return;
        loadingChoices = false;
        updateCourseChoices();
        notice(error.message, true, element("optimizer-notice"));
        element("retry-options").hidden = false;
        element("calculate-plan").disabled = true;
        if (focusResult && document.activeElement === document.body) element("retry-options").focus();
        connection("error");
    } finally {
        if (request === state.request) {
            element("reload-options").disabled = false;
            element("reload-options").textContent = "Refresh options";
        }
    }
}

function showAllocation(result) {
    const summary = element("allocation");
    summary.replaceChildren();
    const hours = (value) => value + (Number(value) === 1 ? " hour" : " hours");
    element("allocation-summary").textContent = "Spend " + hours(result.x) + " on " + result.course_a
        + " and " + hours(result.y) + " on " + result.course_b + ".";
    for (const [label, value] of [
        [result.course_a, hours(result.x)], [result.course_b, hours(result.y)],
        ["Priority score", result.score], ["Unused time", hours(result.unused)],
    ]) {
        const item = create("div");
        item.append(create("dt", label), create("dd", value));
        summary.append(item);
    }
    const corners = element("plan-corners");
    corners.replaceChildren();
    for (const point of result.corners) {
        const row = create("tr");
        for (const value of point) row.append(create("td", value));
        corners.append(row);
    }
    element("plan-result").hidden = false;
    element("corner-results").hidden = false;
}

async function calculatePlan(event) {
    event.preventDefault();
    if (planningRequest || loadingChoices || !element("retry-options").hidden) return;
    clearPlanFeedback();
    const data = Object.fromEntries(new FormData(optimizerForm));
    const controls = [...optimizerForm.querySelectorAll("input, select, button")];
    const missing = controls.filter((input) => input.required && !input.value.trim());
    if (missing.length) {
        for (const input of missing) markPlanField(input.name, "This field is required.");
        notice("Complete the highlighted fields.", true, element("optimizer-notice"));
        missing[0].focus();
        return;
    }
    if (data.course_a === data.course_b) {
        markPlanField("course_b", "Select a different enrolled course.");
        planCourseB.focus();
        return;
    }
    const button = element("calculate-plan");
    const names = [planCourseA.selectedOptions[0].textContent, planCourseB.selectedOptions[0].textContent];
    representPlan(data, names);
    const request = state.request;
    planningRequest = true;
    let resultHeading;
    const feedback = element("optimizer-notice");
    for (const control of controls) control.disabled = true;
    button.replaceChildren(loadingLabel("Calculating…"));
    try {
        const result = await api("/study-time/optimize", "POST", data);
        if (state.page === "optimizer" && request === state.request) {
            showAllocation(result);
            resultHeading = element("result-heading");
        }
    } catch (error) {
        if (state.page === "optimizer" && request === state.request) {
            let general = error.message;
            if (Array.isArray(error.detail)) {
                const unmatched = error.detail.filter((item) => !markPlanField(item.loc?.at(-1), item.msg));
                general = unmatched.map((item) => item.msg).join(" ");
            } else {
                const field = plannerErrorFields.find(([label]) => error.message.startsWith(label + " "));
                if (field && markPlanField(field[1], error.message)) general = "";
            }
            notice(general, true, feedback);
        }
    } finally {
        planningRequest = false;
        for (const control of controls) control.disabled = false;
        for (const select of [planCourseA, planCourseB]) select.disabled = select.options.length < 2;
        element("reload-options").disabled = loadingChoices;
        button.disabled = loadingChoices || planCourseA.options.length < 3;
        button.textContent = "Calculate plan";
        if (state.page === "optimizer" && request === state.request) {
            const target = resultHeading ?? optimizerForm.querySelector('[aria-invalid="true"]')
                ?? (feedback.textContent ? feedback : button);
            target.focus({ preventScroll: true });
            (resultHeading ? element("plan-result") : target).scrollIntoView({ block: "nearest" });
        }
    }
}

planStudent.addEventListener("change", updateCourseChoices);
planCourseA.addEventListener("change", syncCourseOptions);
planCourseB.addEventListener("change", syncCourseOptions);
for (const field of optimizerForm.querySelectorAll("input, select:not(#plan-student)")) {
    field.addEventListener("input", clearPlanFeedback);
}
element("reload-options").addEventListener("click", () => loadOptimizerChoices());
element("retry-options").addEventListener("click", () => loadOptimizerChoices(true));
optimizerForm.addEventListener("submit", calculatePlan);
element("search").addEventListener("input", restartRecordList);
element("department").addEventListener("change", restartRecordList);
element("record-sort").addEventListener("change", (event) => setSort(...event.target.value.split(":")));
element("previous-page").addEventListener("click", () => changeRecordPage(-1));
element("next-page").addEventListener("click", () => changeRecordPage(1));
element("clear-filters").addEventListener("click", () => {
    element("search").value = "";
    element("department").value = "";
    restartRecordList();
    element("search").focus();
});
element("refresh").addEventListener("click", () => { notice(); loadRecords(); });
element("dismiss-notice").addEventListener("click", () => {
    notice();
    element("page-title").focus({ preventScroll: true });
});
element("dismiss-notice").addEventListener("blur", () => {
    if (!element("record-toast").classList.contains("error") && !element("dismiss-notice").hidden) {
        clearTimeout(toastTimer);
        toastTimer = setTimeout(clearSuccessToast, 6000);
    }
});
element("add-record").addEventListener("click", (event) => openEditor("add", null, event.currentTarget));
element("close-editor").addEventListener("click", () => dialog.close());
element("cancel-editor").addEventListener("click", () => dialog.close());
dialog.addEventListener("cancel", (event) => { if (writing) event.preventDefault(); });
dialog.addEventListener("close", () => {
    const opener = editing?.opener;
    const replacement = opener?.dataset.recordAction
        ? findRowButton(opener.dataset.recordAction, opener.dataset.recordId) : null;
    (opener?.isConnected ? opener : replacement ?? element("add-record")).focus();
    element("save-record").disabled = false;
    editing = null;
});
editorForm.addEventListener("submit", saveEditor);

// Use a disclosure where the browser does not support native popovers.
const sidebar = element("sidebar");
const menuButton = element("nav-toggle");
const compactNav = matchMedia("(max-width: 960px)");
const compactFilters = matchMedia("(max-width: 650px)");
const filters = element("filters");
const nativePopover = "popover" in HTMLElement.prototype;

function menuIsOpen() {
    return nativePopover ? sidebar.matches(":popover-open") : sidebar.hasAttribute("data-open");
}

function updateMenu(open) {
    sidebar.toggleAttribute("data-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close workspace menu" : "Open workspace menu");
    element("nav-toggle-text").textContent = open ? "Close" : "Menu";
    if (open) sidebar.querySelector('[aria-current="page"]')?.focus({ preventScroll: true });
}

function closeMenu() {
    if (!menuIsOpen()) return;
    if (nativePopover) sidebar.hidePopover();
    else {
        sidebar.hidden = true;
        updateMenu(false);
    }
}

function syncNavigationLayout() {
    const focused = document.activeElement;
    if (compactNav.matches) {
        if (nativePopover) sidebar.setAttribute("popover", "auto");
        else sidebar.hidden = true;
        if (sidebar.contains(focused)) menuButton.focus({ preventScroll: true });
    } else {
        closeMenu();
        sidebar.removeAttribute("popover");
        sidebar.hidden = false;
        if (focused === menuButton) sidebar.querySelector('[aria-current="page"]')?.focus({ preventScroll: true });
    }
}

if (nativePopover) {
    sidebar.addEventListener("toggle", () => updateMenu(menuIsOpen()));
} else {
    menuButton.removeAttribute("popovertarget");
    menuButton.addEventListener("click", () => {
        if (menuIsOpen()) closeMenu();
        else {
            sidebar.hidden = false;
            updateMenu(true);
        }
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && menuIsOpen()) {
            closeMenu();
            menuButton.focus();
        }
    });
    document.addEventListener("click", (event) => {
        if (menuIsOpen() && !sidebar.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
    });
}

document.addEventListener("focusin", (event) => {
    if (!sidebar.contains(event.target) && !menuButton.contains(event.target)) closeMenu();
});

function followWorkspaceLink(event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("[data-page]");
    if (!link) return;
    closeMenu();
    if (link.dataset.page === state.page) {
        window.scrollTo(0, 0);
        element("page-title").focus({ preventScroll: true });
    }
}

function syncFilterLayout() {
    if (compactFilters.matches && filters.contains(document.activeElement)) filters.querySelector("summary").focus();
    filters.open = !compactFilters.matches;
}

sidebar.addEventListener("click", followWorkspaceLink);
document.querySelector(".site-brand").addEventListener("click", followWorkspaceLink);
compactNav.addEventListener("change", syncNavigationLayout);
compactFilters.addEventListener("change", syncFilterLayout);
syncNavigationLayout();
syncFilterLayout();
window.addEventListener("hashchange", showPage);
showPage();
