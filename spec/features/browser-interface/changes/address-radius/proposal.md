# Address-centered radius controls

Trigger: the user approved an address-and-miles search area with a map preview.

This is a behavior change: the editor hides radius areas and omits their center and mileage when
saving. Expose an address radius form, preview its circle before adding, and preserve every radius
form when saving and reopening. Keep existing polygon editing and include/exclude behavior.

Scope: builder controls, radius serialization in the shared facade, and one thin guarded preview
route. The geography feature owns address lookup and radius calculations. AC-106 and AC-107 are
new; existing AC-2, AC-3, AC-14, AC-17 and AC-22 still apply.
