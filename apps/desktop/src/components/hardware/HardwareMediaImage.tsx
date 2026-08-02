import { useEffect, useState, type ReactNode } from "react";
import type { HardwareMediaAsset } from "@zhangwen/contracts";
import { apiFetch } from "../../services/api";

interface HardwareMediaImageProps {
  asset: HardwareMediaAsset;
  className?: string;
  fallback?: ReactNode;
}

export function HardwareMediaImage({
  asset,
  className,
  fallback = null,
}: HardwareMediaImageProps) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let createdUrl: string | null = null;
    setObjectUrl(null);
    void apiFetch(asset.url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const contentType = response.headers.get("Content-Type")?.split(";", 1)[0];
        if (contentType !== asset.contentType) throw new Error("图片格式不一致");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        createdUrl = URL.createObjectURL(blob);
        setObjectUrl(createdUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setObjectUrl(null);
      });
    return () => {
      controller.abort();
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [asset.contentType, asset.url]);

  if (!objectUrl) return <>{fallback}</>;
  return <img className={className} src={objectUrl} alt={asset.alt} />;
}

export function coverMedia(
  media: HardwareMediaAsset[] | undefined,
): HardwareMediaAsset | null {
  return media?.find((item) => item.role === "cover") ?? null;
}
