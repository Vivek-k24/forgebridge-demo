# PartGraph

PartGraph helps you repair a Honda without discovering halfway through the job that you forgot a mount, seal, clip, hose, fastener, sensor, or other connected part.

**Live app:** https://vivek-k24.github.io/forgebridge-demo/#/

## What PartGraph does

Instead of stopping at “this part fits your car,” PartGraph walks through the repair as an assembly.

```text
Choose your Honda
→ choose the repair area
→ choose the main part
→ check the connected parts and hardware
→ mark what you already have and what you still need
→ open verified purchase paths
```

## How to use it

1. **Choose your Honda manually.** Select the year, model, and available trim/configuration information. Manual selection is the main path.
2. **Or use a VIN.** VIN lookup is optional and can provide additional vehicle identifiers when you want stronger verification.
3. **Choose the repair.** Select the block, sub-block, and main part you are working on.
4. **Use photo help if needed.** If you do not know what a part is called, take or choose a photo on your phone. The current version keeps the photo on your device for comparison.
5. **Check the assembly.** Mark each connected item as **Need**, **Have**, **Inspect**, or **Not sure**. Smaller hardware stays grouped with the part it belongs to.
6. **Find the parts.** Items marked **Need** receive purchase/search paths only after PartGraph has a verified OEM identity for them.

## What vehicle data is used

PartGraph uses public and source-backed vehicle information rather than forcing VIN entry.

- **American Honda published material** is used where available for Honda trim/configuration information.
- **NHTSA vPIC** supplies public Honda model discovery and optional VIN decoding.
- **FuelEconomy.gov (U.S. EPA / Department of Energy)** can provide additional public powertrain/configuration choices for Honda model years it covers.

VIN is a second option, not a requirement for normal browsing.

## Current repair coverage

The vehicle selector can browse more Honda years and models, but the fully verified repair graph is intentionally narrower while the data is being checked.

The strongest current repair coverage is:

**2009 U.S.-market Honda Civic Hybrid / MX Hybrid, KA CVT — front cooling and related assemblies.**

If you select a Honda for which PartGraph has not yet published a verified mechanical graph, the vehicle can still be identified, but repair parts stay locked instead of borrowing parts from another trim or guessing.

## Why PartGraph is careful

A seller saying “fits your vehicle” is not enough. PartGraph separates two jobs:

- **Mechanical identification:** determine the part and its relationship to the exact vehicle/assembly from source-backed records.
- **Shopping:** once the identity is known, find places that sell that exact OEM part or a verified interchange.

PartGraph does not invent torque values, fluid procedures, fitment, or repair instructions from a language model.

## Photos and privacy

The current photo helper uses a browser-local preview. Your selected photo is not uploaded to a PartGraph server by this version.

Repair choices are saved locally in your browser when you use **Save repair**. No payment-card information is collected.

## What is being added next

- more Honda vehicle/assembly coverage
- more source-backed part images
- stronger seller/provider search and caching
- repair specifications only when an authoritative source has been verified
- constrained camera recognition that compares a photo against parts already known to belong to the selected vehicle and assembly

PartGraph is being built around one rule: **when the system does not have enough evidence to identify a part safely, it should say so instead of guessing.**
