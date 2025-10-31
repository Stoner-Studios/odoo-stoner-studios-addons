/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

/**
 * Component that displays a warning banner when user impersonation is active.
 * Similar to Odoo's database expiration warning.
 */
export class ImpersonateWarning extends Component {
    static template = "user_impersonate.ImpersonateWarning";
    static props = {};

    setup() {
        this.orm = this.env.services.orm;
        this.dialog = this.env.services.dialog;
        
        this.state = useState({
            isImpersonating: false,
            originalUser: "",
            targetUser: "",
            visible: true,
        });
        
        onWillStart(async () => {
            await this.checkImpersonation();
        });
        
        // Add body class when impersonating
        useEffect(() => {
            if (this.state.isImpersonating) {
                document.body.classList.add('o_user_impersonating');
                // Adjust for other warnings
                const warnings = document.querySelectorAll('.o_database_warning, .test_mode_warning');
                if (warnings.length > 0) {
                    document.body.style.setProperty('--impersonate-offset', `${warnings.length * 40}px`);
                }
            }
            return () => {
                document.body.classList.remove('o_user_impersonating');
                document.body.style.removeProperty('--impersonate-offset');
            };
        }, () => [this.state.isImpersonating]);
    }
    
    async checkImpersonation() {
        try {
            const result = await this.orm.call("res.users", "check_impersonation_status", []);
            if (result?.is_impersonating) {
                this.state.isImpersonating = true;
                this.state.originalUser = result.original_user || _t("Admin");
                this.state.targetUser = result.target_user || _t("Unknown");
            }
        } catch (error) {
            console.error("[IMPERSONATE WARNING] Error checking status:", error);
        }
    }
    
    async stopImpersonation() {
        this.dialog.add(ConfirmationDialog, {
            body: _t("Are you sure you want to stop impersonating this user?"),
            title: _t("Stop Impersonation"),
            confirm: async () => {
                await this.orm.call("res.users", "action_stop_impersonate", []);
                globalThis.location.reload();
            },
            cancel: () => {},
        });
    }
    
    hideWarning() {
        this.state.visible = false;
        // Remember in session storage
        sessionStorage.setItem('impersonate_warning_hidden', 'true');
    }
}

// Register as a systray component (only if not already registered)
const systrayRegistry = registry.category("systray");
if (!systrayRegistry.contains("user_impersonate.ImpersonateWarning")) {
    systrayRegistry.add(
        "user_impersonate.ImpersonateWarning",
        {
            Component: ImpersonateWarning,
        },
        { sequence: 1 }
    );
}