import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MapPin, DollarSign, Car, Search, ExternalLink } from "lucide-react";
import { api, type Listing } from "../api/client";
import KpiCard from "../components/KpiCard";
import EmptyState from "../components/EmptyState";
import ErrorState from "../components/ErrorState";
import Pagination from "../components/Pagination";
import { SkeletonTable } from "../components/Skeleton";
import { format, parseISO } from "date-fns";
import clsx from "clsx";

const PAGE_SIZE = 20;

function fmt(price: number | null, currency: string) {
  if (price == null) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 0,
  }).format(price);
}

function fmtMileage(km: number | null) {
  if (km == null) return "—";
  return `${km.toLocaleString()} km`;
}

function fmtDate(d: string | null) {
  if (!d) return "—";
  try {
    return format(parseISO(d), "MMM d, yyyy");
  } catch {
    return d;
  }
}

type OriginFilter = "scraped" | "seeded" | "all";

export default function Listings() {
  const [offset, setOffset] = useState(0);
  const [brandFilter, setBrandFilter] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [originFilter, setOriginFilter] = useState<OriginFilter>("scraped");

  const origin = originFilter === "all" ? undefined : originFilter;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["listings", offset, brandFilter, origin],
    queryFn: () =>
      api.listings({
        limit: PAGE_SIZE,
        offset,
        brand: brandFilter || undefined,
        origin,
      }),
    placeholderData: (prev) => prev,
  });

  const { data: summary } = useQuery({
    queryKey: ["listings-summary"],
    queryFn: () => api.listingsSummary(),
    staleTime: 60_000,
  });

  if (isError) {
    return (
      <div className="card">
        <ErrorState error={error} onRetry={refetch} />
      </div>
    );
  }

  const items: Listing[] = data?.items ?? [];
  const total = data?.total ?? 0;

  const avgPrice = summary?.avg_price ?? null;
  const avgMileage = summary?.avg_mileage ?? null;
  const countries = summary?.countries ?? 0;

  const handleSearch = () => {
    setBrandFilter(searchInput.trim());
    setOffset(0);
  };

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          label="Total Listings"
          value={total}
          icon={Car}
          iconColor="text-brand-500"
          loading={isLoading}
        />
        <KpiCard
          label="Avg Listed Price"
          value={avgPrice != null ? `€${Math.round(avgPrice).toLocaleString()}` : "—"}
          sub="EUR listings only"
          icon={DollarSign}
          iconColor="text-emerald-500"
          loading={isLoading}
        />
        <KpiCard
          label="Avg Mileage"
          value={avgMileage != null ? `${Math.round(avgMileage).toLocaleString()} km` : "—"}
          sub="All listings"
          icon={Car}
          iconColor="text-amber-500"
          loading={isLoading}
        />
        <KpiCard
          label="Countries"
          value={countries || "—"}
          sub="All listings"
          icon={MapPin}
          iconColor="text-blue-500"
          loading={isLoading}
        />
      </div>

      {/* Filters */}
      <div className="card p-4 flex flex-wrap items-center gap-3">
        {/* Origin filter */}
        <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg p-1">
          {(["scraped", "all", "seeded"] as OriginFilter[]).map((o) => (
            <button
              key={o}
              onClick={() => { setOriginFilter(o); setOffset(0); }}
              className={clsx(
                "px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
                originFilter === o
                  ? o === "scraped" ? "bg-emerald-500 text-white shadow-sm"
                    : o === "seeded" ? "bg-slate-400 text-white shadow-sm"
                    : "bg-brand-500 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              )}
            >
              {o === "scraped" ? "Live" : o === "seeded" ? "Seeded" : "All"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <Search className="h-4 w-4 text-slate-400 flex-shrink-0" />
          <input
            type="text"
            placeholder="Filter by brand name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
            className="text-input flex-1"
          />
        </div>
        <button onClick={handleSearch} className="btn-primary">
          Search
        </button>
        {brandFilter && (
          <button
            onClick={() => {
              setBrandFilter("");
              setSearchInput("");
              setOffset(0);
            }}
            className="btn-ghost"
          >
            Clear
          </button>
        )}
        {brandFilter && (
          <span className="badge badge-running">
            Brand: {brandFilter}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <SkeletonTable rows={PAGE_SIZE} cols={6} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={MapPin}
            title="No listings found"
            message={
              brandFilter
                ? `No listings match brand "${brandFilter}". Try a different search.`
                : "No marketplace listings have been scraped yet."
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr>
                    <th className="table-th">Dealer</th>
                    <th className="table-th text-right">Price</th>
                    <th className="table-th text-right">Mileage</th>
                    <th className="table-th">Location</th>
                    <th className="table-th">Listed</th>
                    <th className="table-th">Origin</th>
                    <th className="table-th">Link</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((listing) => (
                    <tr key={listing.id} className="table-tr">
                      <td className="table-td font-medium text-slate-800 max-w-[160px] truncate">
                        {listing.dealer_name ?? (
                          <span className="text-slate-400 italic">Unknown</span>
                        )}
                      </td>
                      <td className="table-td text-right tabular-nums">
                        {listing.listed_price != null ? (
                          <span className="font-semibold text-slate-800">
                            {fmt(listing.listed_price, listing.currency)}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="table-td text-right tabular-nums text-slate-600">
                        {fmtMileage(listing.mileage_km)}
                      </td>
                      <td className="table-td">
                        {listing.city || listing.country ? (
                          <span className="flex items-center gap-1 text-slate-600">
                            <MapPin className="h-3 w-3 text-slate-400 flex-shrink-0" />
                            {[listing.city, listing.country].filter(Boolean).join(", ")}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="table-td text-slate-500 whitespace-nowrap">
                        {fmtDate(listing.listed_at)}
                      </td>
                      <td className="table-td">
                        {listing.data_origin === "scraped" ? (
                          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">Live</span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">Seeded</span>
                        )}
                      </td>
                      <td className="table-td">
                        <a
                          href={listing.listing_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-brand-500 hover:text-brand-600 text-xs transition-colors"
                        >
                          <ExternalLink className="h-3 w-3" />
                          View
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              total={total}
              limit={PAGE_SIZE}
              offset={offset}
              onOffsetChange={setOffset}
            />
          </>
        )}
      </div>
    </div>
  );
}
