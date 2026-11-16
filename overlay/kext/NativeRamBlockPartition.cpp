// SPDX-License-Identifier: BSD-2-Clause-Patent
// The Data disk (NativeRamBlock) as a partitioned disk: one partition, at offset 0 over the whole disk, holds the APFS container.
//
// The store is a whole-disk APFS container, a layout no Mac has: there the container lies on a partition of disk0 (GPT). System
// Settings' Storage pane lists volumes the way of a partitioned disk only (Storage.appex's DisksController: DiskManagement's
// partitionChildrenForDisk of every top-level disk, then containerForPhysicalStore of every partition): with no partition it lists no
// volume, never finds the one mounted at /System/Volumes/Data, and stays at "Loading items". This scheme publishes the partition
// (disk0s1) without a partition map on the medium: reads and writes go to the whole disk at the same offsets. Its Content Hint is the
// iBoot System Container's, which AppleAPFSContainerScheme matches like an APFS partition's, and which launchd's mount-phase-1
// (apfs_boot_util) needs on the nearest plain IOMedia above the xART volume (docs/k27-real-disk-layout-plan.md P5).
#include <IOKit/storage/IOPartitionScheme.h>

class NativeRamBlockPartition : public IOPartitionScheme {
  OSDeclareDefaultStructors(NativeRamBlockPartition)
  IOMedia *partition = nullptr;

public:
  IOService *probe(IOService *provider, SInt32 *score) override;
  bool start(IOService *provider) override;
  void stop(IOService *provider) override;
  void free() override;
};
OSDefineMetaClassAndStructors(NativeRamBlockPartition, IOPartitionScheme)

IOService *NativeRamBlockPartition::probe(IOService *provider, SInt32 *score)
{
  // Only the NativeRamBlock disk: the personality matches every whole IOMedia (disk images, APFS containers' own disks too)
  IOMedia *media = OSDynamicCast(IOMedia, provider);
  IOService *driver = media ? media->getProvider() : nullptr;
  IOService *device = driver ? driver->getProvider() : nullptr;
  if (!media || !media->isWhole() || !device || !device->metaCast("NativeRamBlock")) return nullptr;
  return IOPartitionScheme::probe(provider, score);
}

bool NativeRamBlockPartition::start(IOService *provider)
{
  if (!IOPartitionScheme::start(provider)) return false;
  IOMedia *media = getProvider();
  partition = new IOMedia;
  if (!partition) return false;
  if (!partition->init(0, media->getSize(), media->getPreferredBlockSize(), media->getAttributes(), false, media->isWritable(),
                       "69646961-6700-11AA-AA11-00306543ECAC")) {
    partition->release();
    partition = nullptr;
    return false;
  }
  partition->setName("DroidVM Container");
  partition->setProperty(kIOMediaPartitionIDKey, 1, 32);
  partition->setProperty(kIOMediaBaseKey, 0ULL, 64);   // as IOGUIDPartitionScheme's: DiskManagement lists only partitions with a Base
  partition->setLocation("1");
  if (!partition->attach(this)) {
    partition->release();
    partition = nullptr;
    return false;
  }
  partition->registerService();
  return true;
}

void NativeRamBlockPartition::stop(IOService *provider)
{
  if (partition) partition->detach(this);
  IOPartitionScheme::stop(provider);
}

void NativeRamBlockPartition::free()
{
  if (partition) partition->release();
  partition = nullptr;
  IOPartitionScheme::free();
}
